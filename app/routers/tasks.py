"""投稿タスク実行エンドポイント（Cloud Tasks の受け先 = poster）

本番（GCP）では Cloud Tasks がこのエンドポイントを叩く:
  Cloud Tasks キュー（順序実行 maxConcurrentDispatches=1）
    → POST /tasks/execute → 実投稿 → posting_history 更新

⚠️ デプロイ時は CLOUD_RUN_URL 環境変数をこのエンドポイントの URL に
   設定すること（例: https://<cloud-run>/tasks/execute）。
   Cloud Run 側は --no-allow-unauthenticated + OIDC で保護される。
"""
import logging
import os

from fastapi import APIRouter, HTTPException, Request, status

from app.services.poster import execute_task as run_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Cloud Tasks キューの maxAttempts と揃える（posting-queue = 3）
_MAX_ATTEMPTS = int(os.getenv("TASKS_MAX_ATTEMPTS", "3"))


@router.post("/execute")
async def execute_task_endpoint(request: Request):
    """投稿タスクを実行（Cloud Tasks からの HTTP プッシュを受ける）

    リクエストボディは cloud_tasks.py が作る payload:
        {"user_id": int, "case_data": dict, "timestamp": str}

    処理完了までレスポンスを返さない（Cloud Tasks のタイムアウトは
    キュー設定で 1 時間確保済み）。5xx を返すと自動リトライされる。
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不正なリクエストボディです",
        )

    if payload.get("user_id") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id は必須です",
        )

    logger.info(
        f"[Tasks] 実行リクエスト受信: case_id="
        f"{(payload.get('case_data') or {}).get('case_id') or payload.get('case_id')}"
    )
    # Cloud Tasks の試行回数（0 始まり）。手動呼び出し時はヘッダ無し=0。
    retry_count = int(request.headers.get("X-CloudTasks-TaskRetryCount", "0") or "0")

    results = await run_task(payload)

    all_error = bool(results) and all(
        r.get("status") == "error" for r in results.values())

    if all_error:
        is_final = retry_count >= _MAX_ATTEMPTS - 1
        if is_final:
            # リトライ上限に到達 → Dead Letter Queue に退避＋監査ログ＋管理者アラート。
            # ここで 200 を返し、無意味な再試行を止める（捕捉済みのため）。
            from app.db import store
            from app.utils.audit import audit
            try:
                did = store.record_dead_letter(
                    payload.get("kind", "case"), payload.get("action", "register"),
                    payload, error={"results": results}, retry_count=retry_count)
            except Exception as e:
                did = None
                logger.error(f"[Tasks] dead_letter 記録失敗: {e}")
            audit("dead_letter", dead_letter_id=did, retry_count=retry_count,
                  kind=payload.get("kind", "case"), action=payload.get("action"),
                  case_id=(payload.get("case_data") or {}).get("case_id") or payload.get("case_id"))
            logger.error(f"[Tasks] ☠️ リトライ上限到達→DLQ退避 id={did} retry={retry_count}")
            try:
                _alert_dead_letter(payload, results, did)
            except Exception as e:
                logger.error(f"[Tasks] DLQアラート送信失敗: {e}")
            return {"status": "dead_letter", "dead_letter_id": did, "results": results}
        # まだリトライ余地あり → 500 で Cloud Tasks に再試行させる
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "全プラットフォームで投稿失敗", "results": results},
        )

    return {"status": "success", "results": results}


def _alert_dead_letter(payload: dict, results: dict, dead_letter_id) -> None:
    """DLQ 退避を通知。宛先は「投稿した本人の連絡先メール」を最優先し、
    無ければ管理者（ADMIN_ALERT_EMAIL / MAIL_FROM）へ。"""
    try:
        from app.utils.mailer import send_email
    except Exception:
        return
    # 投稿者本人のメール（初期設定の連絡先）を最優先
    to = None
    try:
        uid = payload.get("user_id")
        if uid is not None:
            from app.db import store
            to = (store.get_credentials(uid) or {}).get("contact_email")
    except Exception:
        to = None
    to = to or os.getenv("ADMIN_ALERT_EMAIL") or os.getenv("MAIL_FROM")
    if not to:
        return
    kind = "荷物" if payload.get("kind", "case") == "case" else "空車"
    cid = (payload.get("case_data") or {}).get("case_id") or payload.get("case_id") \
        or payload.get("truck_id")
    body = (f"投稿を3回試しましたが、投稿できませんでした（失敗が確定）。\n\n"
            f"種別: {kind} / {payload.get('action')}\n対象ID: {cid}\n\n"
            f"アプリの「失敗した投稿」画面から、原因を直して再投稿できます:\n"
            f"  {os.getenv('APP_BASE_URL', '').rstrip('/')}/failed/\n\n"
            f"（管理番号 DLQ #{dead_letter_id}）")
    send_email(to, "【Carroo】投稿できませんでした（要確認）", body)
