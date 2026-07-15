"""
プッシュ通知サービス
投稿成功/失敗、バッチ処理の進捗をリアルタイム配信
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """リアルタイム通知管理サービス"""

    def __init__(self):
        # ユーザーID -> 通知キューのマッピング
        self.user_queues: Dict[int, asyncio.Queue] = {}
        # ユーザーID -> アクティブな接続数
        self.active_connections: Dict[int, int] = {}

    async def connect(self, user_id: int) -> asyncio.Queue:
        """ユーザーをSSEストリームに接続"""
        if user_id not in self.user_queues:
            self.user_queues[user_id] = asyncio.Queue()
            self.active_connections[user_id] = 0

        self.active_connections[user_id] += 1
        logger.info(f"[Notification] User {user_id} connected. Active: {self.active_connections[user_id]}")
        return self.user_queues[user_id]

    async def disconnect(self, user_id: int):
        """ユーザーをSSEストリームから切断"""
        if user_id in self.active_connections:
            self.active_connections[user_id] = max(0, self.active_connections[user_id] - 1)
            if self.active_connections[user_id] == 0:
                # キューをクリア
                if user_id in self.user_queues:
                    del self.user_queues[user_id]
                del self.active_connections[user_id]
            logger.info(f"[Notification] User {user_id} disconnected. Active: {self.active_connections.get(user_id, 0)}")

    async def send_notification(self, user_id: int, notification: Dict) -> bool:
        """ユーザーに通知を送信"""
        if user_id not in self.user_queues:
            logger.warning(f"[Notification] User {user_id} not connected, skipping notification")
            return False

        try:
            notification["timestamp"] = datetime.now().isoformat()
            await self.user_queues[user_id].put(notification)
            return True
        except Exception as e:
            logger.error(f"[Notification] Error sending to user {user_id}: {e}")
            return False

    async def notify_posting_started(self, user_id: int, case_id: int, platforms: List[str]):
        """投稿開始通知"""
        notification = {
            "type": "posting_started",
            "status": "info",
            "case_id": case_id,
            "platforms": platforms,
            "message": f"案件 #{case_id} を {', '.join(platforms)} に投稿中..."
        }
        return await self.send_notification(user_id, notification)

    async def notify_posting_completed(self, user_id: int, case_id: int, results: List[Dict]):
        """投稿完了通知"""
        successful = [r["platform"] for r in results if r["status"] == "success"]
        failed = [r["platform"] for r in results if r["status"] == "error"]

        if failed:
            notification = {
                "type": "posting_completed",
                "status": "warning",
                "case_id": case_id,
                "successful_platforms": successful,
                "failed_platforms": failed,
                "message": f"案件 #{case_id}: {', '.join(successful)} に投稿完了、{', '.join(failed)} に失敗",
                "results": results
            }
        else:
            notification = {
                "type": "posting_completed",
                "status": "success",
                "case_id": case_id,
                "successful_platforms": successful,
                "message": f"案件 #{case_id}: すべてのプラットフォームへの投稿が完了しました ✅"
            }

        return await self.send_notification(user_id, notification)

    async def notify_posting_error(self, user_id: int, case_id: int, error: str):
        """投稿エラー通知"""
        notification = {
            "type": "posting_error",
            "status": "error",
            "case_id": case_id,
            "message": f"案件 #{case_id} の投稿エラー: {error}"
        }
        return await self.send_notification(user_id, notification)

    async def notify_batch_progress(self, user_id: int, batch_id: int, progress: int, total: int):
        """バッチ処理の進捗通知"""
        percentage = int((progress / total) * 100) if total > 0 else 0
        notification = {
            "type": "batch_progress",
            "status": "info",
            "batch_id": batch_id,
            "progress": progress,
            "total": total,
            "percentage": percentage,
            "message": f"バッチ処理: {progress}/{total} 完了 ({percentage}%)"
        }
        return await self.send_notification(user_id, notification)

    async def notify_batch_completed(self, user_id: int, batch_id: int, total: int, successful: int):
        """バッチ処理完了通知"""
        failed = total - successful
        notification = {
            "type": "batch_completed",
            "status": "success" if failed == 0 else "warning",
            "batch_id": batch_id,
            "total": total,
            "successful": successful,
            "failed": failed,
            "message": f"バッチ処理完了: {successful}/{total} 成功" + (f"、{failed} 失敗" if failed > 0 else "")
        }
        return await self.send_notification(user_id, notification)


# グローバルインスタンス
notification_service = NotificationService()
