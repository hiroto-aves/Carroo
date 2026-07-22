"""投稿タスク実行エンドポイント（Cloud Tasks の受け先 = poster）

本番（GCP）では Cloud Tasks がこのエンドポイントを叩く:
  Cloud Tasks キュー（順序実行 maxConcurrentDispatches=1）
    → POST /tasks/execute → 実投稿 → posting_history 更新

⚠️ デプロイ時は CLOUD_RUN_URL 環境変数をこのエンドポイントの URL に
   設定すること（例: https://<cloud-run>/tasks/execute）。
   Cloud Run 側は --no-allow-unauthenticated + OIDC で保護される。
"""
import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.services.poster import execute_task as run_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


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
    results = await run_task(payload)

    # 全プラットフォーム失敗の場合は 500 を返して Cloud Tasks にリトライさせる
    if results and all(
        r.get("status") == "error" for r in results.values()
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "全プラットフォームで投稿失敗", "results": results},
        )

    return {"status": "success", "results": results}
