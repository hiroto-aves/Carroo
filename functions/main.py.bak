"""
Cloud Run ポスター関数
Google Cloud Tasks からのリクエストを受け取り、Playwright で投稿処理を実行

デプロイ方法:
  gcloud run deploy poster \\
    --source . \\
    --platform managed \\
    --region us-central1 \\
    --memory 2Gi \\
    --cpu 1 \\
    --timeout 3600 \\
    --max-instances 1 \\
    --no-allow-unauthenticated \\
    --set-env-vars GCP_PROJECT_ID=your-project-id
"""

import functions_framework
from flask import Request
import json
import logging
import asyncio
import os
import sys
from datetime import datetime

# Carroo アプリケーションモジュールをインポート
sys.path.insert(0, os.path.dirname(__file__))

from app.db.database import get_db_connection
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@functions_framework.http
def post_to_platforms(request: Request):
    """
    Google Cloud Tasks から呼び出される HTTP 関数
    複数プラットフォームへの非同期投稿処理を実行

    Request Body:
    {
        "user_id": 1,
        "case_data": {
            "case_id": 123,
            "pick_location": "東京都",
            ...
            "post_to_trabox": true,
            "post_to_webkit": true
        },
        "timestamp": "2026-07-16T12:34:56.789Z"
    }
    """

    try:
        # リクエストボディをパース
        payload = request.get_json()
        if not payload:
            return {"error": "No JSON payload"}, 400

        user_id = payload.get("user_id")
        case_data = payload.get("case_data", {})
        case_id = case_data.get("case_id")

        logger.info(f"🚀 投稿処理開始: Case ID {case_id}, User ID {user_id}")

        # 非同期処理を実行
        result = asyncio.run(_process_posting(case_id, user_id, case_data))

        logger.info(f"✅ 投稿処理完了: {result}")
        return result, 200

    except Exception as e:
        logger.error(f"❌ エラー: {type(e).__name__}: {e}")
        return {
            "error": str(e),
            "type": type(e).__name__,
            "timestamp": datetime.now().isoformat()
        }, 500


async def _process_posting(case_id: int, user_id: int, case_data: dict) -> dict:
    """
    投稿処理（非同期）
    複数プラットフォームへ並行投稿

    Args:
        case_id: 案件 ID
        user_id: ユーザー ID
        case_data: 案件データ

    Returns:
        投稿結果
    """

    conn = get_db_connection()
    cursor = conn.cursor()
    results = []

    try:
        # 投稿タスクを構築
        posting_tasks = []

        # トラボックス投稿
        if case_data.get("post_to_trabox") and settings.TRABOX_TEST_USERNAME:
            logger.info(f"📦 トラボックス投稿開始: Case ID {case_id}")

            case_data_trabox = case_data.copy()
            case_data_trabox["username"] = settings.TRABOX_TEST_USERNAME
            case_data_trabox["password"] = settings.TRABOX_TEST_PASSWORD

            trabox = TraboxAutomation()

            async def post_trabox_task():
                try:
                    result = await trabox.post_case(case_data_trabox)
                    logger.info(f"✅ トラボックス投稿成功: {result}")

                    # DB に記録
                    cursor.execute(
                        "UPDATE posting_history SET status = ?, updated_at = ? WHERE case_id = ? AND platform = ?",
                        (
                            result.get("status", "error"),
                            datetime.now().isoformat(),
                            case_id,
                            "trabox"
                        )
                    )
                    if result.get("status") == "error":
                        cursor.execute(
                            "UPDATE posting_history SET error_message = ? WHERE case_id = ? AND platform = ?",
                            (result.get("message"), case_id, "trabox")
                        )
                    conn.commit()

                    return {
                        "platform": "trabox",
                        "status": result.get("status"),
                        "message": result.get("message")
                    }
                except Exception as e:
                    logger.error(f"❌ トラボックス投稿エラー: {e}")
                    cursor.execute(
                        "UPDATE posting_history SET status = ?, error_message = ?, updated_at = ? WHERE case_id = ? AND platform = ?",
                        ("error", str(e), datetime.now().isoformat(), case_id, "trabox")
                    )
                    conn.commit()
                    raise

            posting_tasks.append(post_trabox_task())

        # WebKIT 投稿
        if case_data.get("post_to_webkit") and settings.WEBKIT_LOGIN_ID:
            logger.info(f"🌐 WebKIT 投稿開始: Case ID {case_id}")

            webkit = WebkitAutomation()

            async def post_webkit_task():
                try:
                    result = await webkit.post_case(case_data)
                    logger.info(f"✅ WebKIT 投稿成功: {result}")

                    # DB に記録
                    cursor.execute(
                        "UPDATE posting_history SET status = ?, updated_at = ? WHERE case_id = ? AND platform = ?",
                        (
                            result.get("status", "error"),
                            datetime.now().isoformat(),
                            case_id,
                            "webkit"
                        )
                    )
                    if result.get("status") == "error":
                        cursor.execute(
                            "UPDATE posting_history SET error_message = ? WHERE case_id = ? AND platform = ?",
                            (result.get("message"), case_id, "webkit")
                        )
                    conn.commit()

                    return {
                        "platform": "webkit",
                        "status": result.get("status"),
                        "message": result.get("message")
                    }
                except Exception as e:
                    logger.error(f"❌ WebKIT 投稿エラー: {e}")
                    cursor.execute(
                        "UPDATE posting_history SET status = ?, error_message = ?, updated_at = ? WHERE case_id = ? AND platform = ?",
                        ("error", str(e), datetime.now().isoformat(), case_id, "webkit")
                    )
                    conn.commit()
                    raise

            posting_tasks.append(post_webkit_task())

        # 並行投稿を実行
        if posting_tasks:
            results = await asyncio.gather(*posting_tasks, return_exceptions=True)

        # 結果をまとめる
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
        failed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "error")
        errors = [r for r in results if isinstance(r, Exception)]

        summary = {
            "case_id": case_id,
            "user_id": user_id,
            "total_platforms": len(results),
            "successful": successful,
            "failed": failed,
            "errors": len(errors),
            "timestamp": datetime.now().isoformat(),
            "details": [r for r in results if isinstance(r, dict)]
        }

        if errors:
            logger.warning(f"⚠️ エラー発生: {errors}")
            summary["error_details"] = [str(e) for e in errors]

        return summary

    except Exception as e:
        logger.error(f"❌ 投稿処理中の予期しないエラー: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # ローカルテスト用
    test_payload = {
        "user_id": 1,
        "case_data": {
            "case_id": 999,
            "pick_location": "東京都",
            "drop_location": "大阪府",
            "cargo_weight": 100.0,
            "vehicle_type": "small_truck",
            "freight_rate": 50000,
            "pickup_date": "2026-07-20",
            "pickup_time": "10:00",
            "post_to_trabox": False,
            "post_to_webkit": False
        },
        "timestamp": datetime.now().isoformat()
    }

    class MockRequest:
        def get_json(self):
            return test_payload

    print(post_to_platforms(MockRequest()))
