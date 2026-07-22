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


def build_result_email(case_data: Dict[str, Any], results: Dict[str, Any]) -> tuple:
    """投稿結果メールの (件名, 本文) を組み立てる

    Trabox / WebKit それぞれの成否を分けて、両方まとめて1通にする。
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

    subject = f"【Carroo】投稿結果: {summary}（案件ID {case_id}）"

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
    for platform, result in results.items():
        name = platform_names.get(platform, platform)
        if result.get("status") == "success":
            lines.append(f"  ✅ {name}: 成功")
            if result.get("baggage_no"):
                lines.append(f"      荷物番号: {result['baggage_no']}")
        else:
            lines.append(f"  ❌ {name}: 失敗")
            message = (result.get("message") or "")[:200]
            if message:
                lines.append(f"      理由: {message}")
    lines += [
        "",
        "投稿状況の詳細はダッシュボードでご確認ください。",
    ]
    return subject, "\n".join(lines)


def _send_result_email(
    user_id: int, case_data: Dict[str, Any], results: Dict[str, Any]
) -> None:
    """投稿結果メールを送信（失敗しても投稿処理は失敗させない）"""
    try:
        from app.utils.mailer import send_email

        to_address = _get_notification_email(user_id)
        if not to_address:
            logger.warning(
                f"[Poster] 通知先メール未登録のため送信スキップ: user_id={user_id}"
            )
            return
        subject, body = build_result_email(case_data, results)
        send_email(to_address, subject, body)
    except Exception as e:
        logger.error(f"[Poster] 結果メール送信処理でエラー（投稿は完了済み）: {e}")
