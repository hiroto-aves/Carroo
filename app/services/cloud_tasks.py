"""
Google Cloud Tasks クライアント
非同期投稿タスクをキューに追加
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)


class GoogleCloudTasksClient:
    """Google Cloud Tasks キュー管理クライアント"""

    def __init__(self, project_id: str, queue_name: str = "posting-queue", region: str = "us-central1"):
        """
        初期化

        Args:
            project_id: GCP プロジェクトID
            queue_name: Cloud Tasks キュー名
            region: リージョン
        """
        self.project_id = project_id
        self.queue_name = queue_name
        self.region = region
        self.client = tasks_v2.CloudTasksClient()
        self.parent = self.client.queue_path(project_id, region, queue_name)

    def add_posting_task(
        self,
        case_data: Dict[str, Any],
        user_id: int,
        scheduled_time: Optional[datetime] = None
    ) -> str:
        """
        投稿タスクをキューに追加

        Args:
            case_data: 案件データ
            user_id: ユーザーID
            scheduled_time: スケジュール時刻（未指定なら即座に実行）

        Returns:
            タスク名
        """

        # ペイロード構築
        payload = {
            "user_id": user_id,
            "case_data": case_data,
            "timestamp": datetime.now().isoformat()
        }

        # Cloud Run 相手先 URL（環境変数から取得）
        # ローカル開発: http://localhost:8001
        # 本番: https://region-project-id.cloudfunctions.net/poster
        cloud_run_url = os.getenv(
            "CLOUD_RUN_URL",
            "https://us-central1-{}.cloudfunctions.net/poster".format(self.project_id)
        )

        # タスク定義
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": cloud_run_url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": f"{self.project_id}@appspot.gserviceaccount.com"
                },
            }
        }

        # スケジュール設定（未指定なら即座に実行）
        if scheduled_time:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(scheduled_time)
            task["schedule_time"] = timestamp

        # タスクを作成
        try:
            response = self.client.create_task(request={"parent": self.parent, "task": task})
            task_name = response.name
            logger.info(f"✅ タスク作成: {task_name}")
            return task_name

        except Exception as e:
            logger.error(f"❌ タスク作成失敗: {e}")
            raise

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        キューの統計情報を取得

        Returns:
            キュー統計
        """
        try:
            queue = self.client.get_queue(request={"name": self.parent})
            return {
                "name": queue.name,
                "state": queue.state,
                "task_count": getattr(queue, "task_count", None),
                "created_time": queue.create_time,
            }
        except Exception as e:
            logger.error(f"❌ キュー統計取得失敗: {e}")
            raise


class LocalTaskQueue:
    """
    ローカル開発用タスクキュー
    Cloud Tasks の代わりにメモリ内キューを使用
    """

    def __init__(self):
        """初期化"""
        self.tasks = []

    def add_posting_task(
        self,
        case_data: Dict[str, Any],
        user_id: int,
        scheduled_time: Optional[datetime] = None
    ) -> str:
        """
        タスクをメモリキューに追加

        Args:
            case_data: 案件データ
            user_id: ユーザーID
            scheduled_time: スケジュール時刻

        Returns:
            タスク ID
        """

        task_id = f"local-task-{len(self.tasks)}"
        task = {
            "id": task_id,
            "user_id": user_id,
            "case_data": case_data,
            "created_at": datetime.now().isoformat(),
            "scheduled_at": scheduled_time.isoformat() if scheduled_time else None,
            "status": "pending"
        }
        self.tasks.append(task)
        logger.info(f"📋 ローカルタスク追加: {task_id}")

        # ローカル開発では即座にバックグラウンドで投稿を実行する
        # （本番の Cloud Tasks → /tasks/execute と同じ処理を in-process で行う）
        try:
            import asyncio
            from app.services.poster import execute_posting_task
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    execute_posting_task(
                        {"user_id": user_id, "case_data": case_data}
                    )
                )
                task["status"] = "dispatched"
                logger.info(f"🚀 ローカル実行開始（バックグラウンド）: {task_id}")
            else:
                logger.warning("イベントループ未稼働のためタスクは保存のみ")
        except Exception as e:
            logger.error(f"ローカル実行の起動失敗: {e}")

        return task_id

    def get_queue_stats(self) -> Dict[str, Any]:
        """キュー統計"""
        return {
            "task_count": len(self.tasks),
            "pending": len([t for t in self.tasks if t["status"] == "pending"]),
            "completed": len([t for t in self.tasks if t["status"] == "completed"])
        }


def get_task_client() -> Union[GoogleCloudTasksClient, LocalTaskQueue]:
    """
    タスククライアントを取得
    環境に応じて Cloud Tasks または ローカルキューを返す
    """

    gcp_project_id = os.getenv("GCP_PROJECT_ID")

    if gcp_project_id:
        logger.info("🌩️ Cloud Tasks クライアントを使用")
        return GoogleCloudTasksClient(gcp_project_id)
    else:
        logger.info("📋 ローカルタスクキューを使用")
        return LocalTaskQueue()
