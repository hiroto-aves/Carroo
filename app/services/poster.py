"""投稿実行サービス（poster）

キューに追加された投稿タスクを実際に実行し、結果を posting_history に記録する。

【呼び出し経路】
- ローカル開発: LocalTaskQueue がタスク追加と同時にバックグラウンド実行
- 本番（GCP）: Cloud Tasks → POST /tasks/execute → 本サービス

【結果の記録】
- 成功: posting_history.status = success、baggage_no に Trabox の荷物番号
- 失敗: posting_history.status = error、error_message に理由
  （pending レコードを update_posting_result() で更新する）
"""
import logging
import os
from typing import Any, Dict

from app.db.database import get_db_connection, update_posting_result

logger = logging.getLogger(__name__)


def _get_trabox_credentials(user_id: int) -> tuple:
    """Trabox 認証情報を取得

    優先順: ユーザーの初期設定（user_credentials・暗号化保存）→ .env のテストアカウント
    """
    conn = get_db_connection()
    row = conn.execute(
        """SELECT trabox_username, trabox_password_encrypted
           FROM user_credentials WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    conn.close()

    if row and row[0] and row[1]:
        try:
            from app.utils.encryption import decrypt_password
            return row[0], decrypt_password(row[1])
        except Exception as e:
            logger.warning(f"[Poster] 認証情報の復号失敗 → .env にフォールバック: {e}")

    username = os.getenv("TRABOX_TEST_USERNAME", "")
    password = os.getenv("TRABOX_TEST_PASSWORD", "")
    if not username or not password:
        raise ValueError(
            "Trabox の認証情報がありません。初期設定画面で登録するか "
            ".env に TRABOX_TEST_USERNAME/PASSWORD を設定してください"
        )
    return username, password


async def execute_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """タスクを action に応じて振り分ける（register / update / delete）

    payload:
      register: {"action":"register", "user_id", "case_data"}
      update  : {"action":"update", "user_id", "case_id", "case_data", "platforms":[...]}
      delete  : {"action":"delete", "user_id", "case_id", "platforms":[...]}
    action 省略時は register（後方互換）。
    """
    action = payload.get("action", "register")
    if action == "update":
        return await execute_update_task(payload)
    if action == "delete":
        return await execute_delete_task(payload)
    return await execute_posting_task(payload)


async def execute_posting_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """投稿タスクを実行し、posting_history を結果で更新する

    Args:
        payload: {"user_id": int, "case_data": dict}
                 case_data には post_to_trabox / post_to_webkit フラグを含む

    Returns:
        {"trabox": {...}, "webkit": {...}} プラットフォームごとの実行結果
    """
    user_id = payload["user_id"]
    case_data = payload["case_data"]
    case_id = case_data.get("case_id")
    results: Dict[str, Any] = {}

    logger.info(f"[Poster] 投稿タスク実行開始: case_id={case_id}")

    # --- Trabox ---
    if case_data.get("post_to_trabox"):
        try:
            from app.automations.trabox import TraboxAutomation

            username, password = _get_trabox_credentials(user_id)
            automation = TraboxAutomation(
                user_id=user_id,
                case_id=case_id,
                username=username,
                password=password,
            )
            result = await automation.post_case(case_data)
            update_posting_result(
                case_id, "trabox", "success",
                baggage_no=result.get("baggage_no"),
            )
            results["trabox"] = result
            logger.info(
                f"[Poster] Trabox 投稿成功: case_id={case_id} "
                f"baggage_no={result.get('baggage_no')}"
            )
        except Exception as e:
            error_msg = str(e)[:500]
            update_posting_result(
                case_id, "trabox", "error", error_message=error_msg
            )
            results["trabox"] = {"status": "error", "message": error_msg}
            logger.error(f"[Poster] Trabox 投稿失敗: case_id={case_id} {error_msg}")

    # --- WebKit ---
    if case_data.get("post_to_webkit"):
        try:
            from app.automations.webkit import WebkitAutomation

            # 担当者IDはユーザーごと（初期設定画面で登録）。apikey は env 共通。
            automation = WebkitAutomation(person_id=_get_webkit_person_id(user_id))
            result = await automation.post_case(case_data)
            status = result.get("status", "success")
            update_posting_result(
                case_id, "webkit",
                "success" if status == "success" else "error",
                baggage_no=result.get("baggage_no"),  # WebKit の伝票番号
                error_message=None if status == "success" else result.get("message"),
            )
            results["webkit"] = result
            logger.info(f"[Poster] WebKit 投稿結果: case_id={case_id} {status}")
        except Exception as e:
            error_msg = str(e)[:500]
            update_posting_result(
                case_id, "webkit", "error", error_message=error_msg
            )
            results["webkit"] = {"status": "error", "message": error_msg}
            logger.error(f"[Poster] WebKit 投稿失敗: case_id={case_id} {error_msg}")

    # --- 結果通知メール（Trabox/WebKit の成否をまとめて1通） ---
    if results:
        _send_result_email(user_id, case_data, results)

    logger.info(f"[Poster] 投稿タスク実行完了: case_id={case_id}")
    return results


def _get_webkit_person_id(user_id: int) -> str:
    """ユーザーの WebKIT 担当者ID（初期設定で登録）を取得。未設定なら env にフォールバック"""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT webkit_person_id FROM user_credentials WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return (row[0] or "") if row and row[0] else ""


def _get_notification_email(user_id: int) -> str:
    """通知先メールアドレス（初期設定画面で登録した連絡先メール）を取得"""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT contact_email FROM user_credentials WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return (row[0] or "") if row else ""


def build_result_email(case_data: Dict[str, Any], results: Dict[str, Any],
                       action_label: str = "投稿") -> tuple:
    """結果メールの (件名, 本文) を組み立てる

    Trabox / WebKit それぞれの成否を分けて、両方まとめて1通にする。
    action_label: 投稿 / 変更 / 削除
    """
    case_id = case_data.get("case_id")
    platform_names = {"trabox": "トラボックス", "webkit": "WebKit"}

    success_count = sum(1 for r in results.values() if r.get("status") == "success")
    fail_count = len(results) - success_count
    if fail_count == 0:
        summary = "すべて成功"
    elif success_count == 0:
        summary = "すべて失敗"
    else:
        summary = f"成功 {success_count} 件・失敗 {fail_count} 件"

    subject = f"【Carroo】{action_label}結果: {summary}（案件ID {case_id}）"

    lines = [
        "Carroo 投稿システムからの自動通知です。",
        "",
        "■ 案件内容",
        f"  案件ID    : {case_id}",
        f"  積地      : {case_data.get('pick_location', '-')}",
        f"  卸地      : {case_data.get('drop_location', '-')}",
        f"  積み日    : {case_data.get('pickup_date', '-')} {case_data.get('pickup_time') or ''}".rstrip(),
        f"  運賃      : "
        + ("要相談" if case_data.get("freight_negotiable")
           else f"{int(float(case_data.get('freight_rate', 0))):,} 円（税別）"),
        "",
        "■ 投稿結果",
    ]
    lines[-1] = f"■ {action_label}結果"
    for platform, result in results.items():
        name = platform_names.get(platform, platform)
        if result.get("status") == "success":
            lines.append(f"  ✅ {name}: 成功")
            if result.get("baggage_no"):
                label = "伝票番号" if platform == "webkit" else "荷物番号"
                lines.append(f"      {label}: {result['baggage_no']}")
        else:
            lines.append(f"  ❌ {name}: 失敗")
            message = (result.get("message") or "")[:200]
            if message:
                lines.append(f"      理由: {message}")
    lines += [
        "",
        "詳細はダッシュボードの案件管理画面でご確認ください。",
    ]
    return subject, "\n".join(lines)


def _send_result_email(
    user_id: int, case_data: Dict[str, Any], results: Dict[str, Any],
    action_label: str = "投稿",
) -> None:
    """結果メールを送信（失敗しても処理は失敗させない）"""
    try:
        from app.utils.mailer import send_email

        to_address = _get_notification_email(user_id)
        if not to_address:
            logger.warning(
                f"[Poster] 通知先メール未登録のため送信スキップ: user_id={user_id}"
            )
            return
        subject, body = build_result_email(case_data, results, action_label)
        send_email(to_address, subject, body)
    except Exception as e:
        logger.error(f"[Poster] 結果メール送信処理でエラー（処理は完了済み）: {e}")


# ============ 変更（update）・削除（delete）タスク ============

def _load_case_data(case_id: int, user_id: int) -> Dict[str, Any]:
    """cases から case_data を組み立て（extras をフラットにマージ）"""
    import json as _json
    conn = get_db_connection()
    row = conn.execute(
        """SELECT id, pick_location, drop_location, cargo_weight, vehicle_type,
                  freight_rate, pickup_date, pickup_time, contact_name,
                  contact_phone, contact_email, extras
           FROM cases WHERE id = ? AND user_id = ?""",
        (case_id, user_id),
    ).fetchone()
    conn.close()
    if not row:
        return {}
    cd = {
        "case_id": row[0], "pick_location": row[1], "drop_location": row[2],
        "cargo_weight": row[3], "vehicle_type": row[4], "freight_rate": row[5],
        "pickup_date": row[6], "pickup_time": row[7], "contact_name": row[8],
        "contact_phone": row[9], "contact_email": row[10],
    }
    if row[11]:
        try:
            cd.update(_json.loads(row[11]))
        except (ValueError, TypeError):
            pass
    return cd


async def execute_update_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """変更タスク: 指定プラットフォームの掲載を更新し、履歴に update を追記"""
    from app.db.database import get_active_baggage_no, update_posting_result

    user_id = payload["user_id"]
    case_id = payload["case_id"]
    platforms = payload.get("platforms", [])
    # 更新後の完全な案件データ（cases から再構築。UI で cases 側は更新済み前提）
    case_data = payload.get("case_data") or _load_case_data(case_id, user_id)
    case_data["case_id"] = case_id
    results: Dict[str, Any] = {}
    logger.info(f"[Poster] 変更タスク: case_id={case_id} platforms={platforms}")

    for platform in platforms:
        baggage_no = get_active_baggage_no(case_id, platform)
        if not baggage_no:
            msg = "掲載中の番号が見つかりません（未登録または削除済み）"
            update_posting_result(case_id, platform, "error",
                                  error_message=msg, action="update")
            results[platform] = {"status": "error", "message": msg}
            continue
        try:
            if platform == "trabox":
                from app.automations.trabox import TraboxAutomation
                username, password = _get_trabox_credentials(user_id)
                auto = TraboxAutomation(user_id=user_id, case_id=case_id,
                                        username=username, password=password)
                result = await auto.update_case(baggage_no, case_data)
            else:  # webkit
                from app.automations.webkit import WebkitAutomation
                auto = WebkitAutomation(person_id=_get_webkit_person_id(user_id))
                result = await auto.update_case(baggage_no, case_data)
            st = result.get("status", "success")
            update_posting_result(
                case_id, platform, "success" if st == "success" else "error",
                baggage_no=baggage_no,
                error_message=None if st == "success" else result.get("message"),
                action="update",
            )
            results[platform] = result
            logger.info(f"[Poster] {platform} 変更結果: {st}")
        except Exception as e:
            msg = str(e)[:500]
            update_posting_result(case_id, platform, "error",
                                  error_message=msg, action="update")
            results[platform] = {"status": "error", "message": msg}
            logger.error(f"[Poster] {platform} 変更失敗: {msg}")

    if results:
        _send_result_email(user_id, case_data, results, action_label="変更")
    return results


async def execute_delete_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """削除タスク: 指定プラットフォームの掲載を削除し、履歴に delete を追記

    削除しても register の履歴行は残る（追記式）。
    """
    from app.db.database import get_active_baggage_no, update_posting_result

    user_id = payload["user_id"]
    case_id = payload["case_id"]
    platforms = payload.get("platforms", [])
    case_data = _load_case_data(case_id, user_id)
    case_data["case_id"] = case_id
    results: Dict[str, Any] = {}
    logger.info(f"[Poster] 削除タスク: case_id={case_id} platforms={platforms}")

    for platform in platforms:
        baggage_no = get_active_baggage_no(case_id, platform)
        if not baggage_no:
            msg = "削除対象の番号が見つかりません（未登録または削除済み）"
            update_posting_result(case_id, platform, "error",
                                  error_message=msg, action="delete")
            results[platform] = {"status": "error", "message": msg}
            continue
        try:
            if platform == "trabox":
                from app.automations.trabox import TraboxAutomation
                username, password = _get_trabox_credentials(user_id)
                auto = TraboxAutomation(user_id=user_id, case_id=case_id,
                                        username=username, password=password)
                result = await auto.delete_case(baggage_no)
            else:  # webkit
                from app.automations.webkit import WebkitAutomation
                auto = WebkitAutomation(person_id=_get_webkit_person_id(user_id))
                result = await auto.delete_case(baggage_no)
            st = result.get("status", "success")
            # 削除成功時も baggage_no を残す（どの番号を消したか履歴に記録）
            update_posting_result(
                case_id, platform, "success" if st == "success" else "error",
                baggage_no=baggage_no,
                error_message=None if st == "success" else result.get("message"),
                action="delete",
            )
            results[platform] = result
            logger.info(f"[Poster] {platform} 削除結果: {st}")
        except Exception as e:
            msg = str(e)[:500]
            update_posting_result(case_id, platform, "error",
                                  error_message=msg, action="delete")
            results[platform] = {"status": "error", "message": msg}
            logger.error(f"[Poster] {platform} 削除失敗: {msg}")

    if results:
        _send_result_email(user_id, case_data, results, action_label="削除")
    return results
