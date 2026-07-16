"""
Cloud Functions エントリーポイント
シンプルな HTTP エンドポイント
"""

import functions_framework
from flask import Request
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functions_framework.http
def post_to_platforms(request: Request):
    """
    シンプルな HTTP エンドポイント
    Cloud Tasks からのリクエストを受け取る
    """

    try:
        payload = request.get_json()

        logger.info(f"✅ リクエスト受信: {payload}")

        # 応答を返す
        return {
            "status": "success",
            "message": "Request received",
            "case_id": payload.get("case_data", {}).get("case_id"),
            "timestamp": "2026-07-16T13:00:00Z"
        }, 200

    except Exception as e:
        logger.error(f"❌ エラー: {e}")
        return {
            "status": "error",
            "message": str(e)
        }, 500
