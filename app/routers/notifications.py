"""
プッシュ通知ルーター
SSE（Server-Sent Events）によるリアルタイム通知配信
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
import logging

from app.dependencies import get_current_user
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/subscribe")
async def subscribe_notifications(current_user: dict = Depends(get_current_user)):
    """SSEストリームに接続して通知を受信"""
    user_id = current_user["id"]

    async def event_generator():
        """通知キューからメッセージを読み込んでSSE形式で配信"""
        queue = await notification_service.connect(user_id)

        try:
            # 接続確認メッセージ
            yield f"data: {json.dumps({'type': 'connected', 'status': 'success', 'message': f'ユーザー {user_id} が接続しました'})}\n\n"

            while True:
                try:
                    # キューから通知を取得（タイムアウト付き）
                    notification = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(notification)}\n\n"
                except asyncio.TimeoutError:
                    # キープアライブ（心拍信号）
                    yield ": keepalive\n\n"

        except Exception as e:
            logger.error(f"[SSE] Error in event generator for user {user_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'status': 'error', 'message': str(e)})}\n\n"

        finally:
            await notification_service.disconnect(user_id)
            logger.info(f"[SSE] Stream closed for user {user_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.post("/test")
async def test_notification(current_user: dict = Depends(get_current_user)):
    """テスト通知を送信"""
    user_id = current_user["id"]
    notification = {
        "type": "test",
        "status": "success",
        "message": "これはテスト通知です。正常に接続されています。 ✅"
    }
    success = await notification_service.send_notification(user_id, notification)
    return {"sent": success, "user_id": user_id}
