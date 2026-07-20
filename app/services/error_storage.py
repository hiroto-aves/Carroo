"""エラーログとスクリーンショットのストレージ管理"""
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LocalErrorStorage:
    """ローカルファイルシステムへのエラーログ保存"""

    def __init__(self, base_dir: str = "debug_logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_error_log(
        self, trace_id: str, error_log: Dict[str, Any]
    ) -> Optional[str]:
        """エラーログを JSON で保存"""
        try:
            date_dir = self.base_dir / datetime.utcnow().strftime("%Y-%m-%d")
            trace_dir = date_dir / trace_id
            trace_dir.mkdir(parents=True, exist_ok=True)

            log_file = trace_dir / "error.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(error_log, f, ensure_ascii=False, indent=2)

            logger.info(f"エラーログを保存: {log_file}")
            return str(log_file)
        except Exception as e:
            logger.error(f"エラーログ保存エラー: {e}")
            return None

    def save_screenshot(
        self, trace_id: str, step_name: str, screenshot_bytes: bytes
    ) -> Optional[str]:
        """スクリーンショットを保存"""
        try:
            date_dir = self.base_dir / datetime.utcnow().strftime("%Y-%m-%d")
            trace_dir = date_dir / trace_id
            trace_dir.mkdir(parents=True, exist_ok=True)

            screenshot_file = trace_dir / f"screenshot_{step_name}.png"
            with open(screenshot_file, "wb") as f:
                f.write(screenshot_bytes)

            logger.info(f"スクリーンショットを保存: {screenshot_file}")
            return str(screenshot_file)
        except Exception as e:
            logger.error(f"スクリーンショット保存エラー: {e}")
            return None

    def save_dom_snapshot(
        self, trace_id: str, dom_html: str
    ) -> Optional[str]:
        """DOM スナップショットを保存"""
        try:
            date_dir = self.base_dir / datetime.utcnow().strftime("%Y-%m-%d")
            trace_dir = date_dir / trace_id
            trace_dir.mkdir(parents=True, exist_ok=True)

            dom_file = trace_dir / "dom_snapshot.html"
            with open(dom_file, "w", encoding="utf-8") as f:
                f.write(dom_html)

            logger.info(f"DOM スナップショットを保存: {dom_file}")
            return str(dom_file)
        except Exception as e:
            logger.error(f"DOM スナップショット保存エラー: {e}")
            return None

    def get_trace_dir(self, trace_id: str) -> Optional[Path]:
        """トレースディレクトリパスを取得"""
        date_dir = self.base_dir / datetime.utcnow().strftime("%Y-%m-%d")
        trace_dir = date_dir / trace_id
        return trace_dir if trace_dir.exists() else None


class CloudErrorStorage:
    """Google Cloud Storage へのエラーログ保存（将来実装）"""

    def __init__(self, bucket_name: str = "carroo-error-logs"):
        self.bucket_name = bucket_name
        self.client = None
        try:
            from google.cloud import storage

            self.client = storage.Client()
            logger.info(f"Cloud Storage クライアントを初期化: {bucket_name}")
        except Exception as e:
            logger.warning(f"Cloud Storage クライアント初期化エラー: {e}")

    def save_error_log(
        self, trace_id: str, error_log: Dict[str, Any]
    ) -> Optional[str]:
        """エラーログを Cloud Storage に保存"""
        if not self.client:
            logger.warning("Cloud Storage クライアントが利用不可です")
            return None

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob_path = (
                f"{datetime.utcnow().strftime('%Y-%m-%d')}/{trace_id}/error.json"
            )
            blob = bucket.blob(blob_path)
            blob.upload_from_string(
                json.dumps(error_log, ensure_ascii=False, indent=2),
                content_type="application/json",
            )
            url = f"gs://{self.bucket_name}/{blob_path}"
            logger.info(f"エラーログを Cloud Storage に保存: {url}")
            return url
        except Exception as e:
            logger.error(f"Cloud Storage 保存エラー: {e}")
            return None

    def save_screenshot(
        self, trace_id: str, step_name: str, screenshot_bytes: bytes
    ) -> Optional[str]:
        """スクリーンショットを Cloud Storage に保存"""
        if not self.client:
            logger.warning("Cloud Storage クライアントが利用不可です")
            return None

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob_path = (
                f"{datetime.utcnow().strftime('%Y-%m-%d')}/{trace_id}/screenshot_{step_name}.png"
            )
            blob = bucket.blob(blob_path)
            blob.upload_from_string(screenshot_bytes, content_type="image/png")
            url = f"gs://{self.bucket_name}/{blob_path}"
            logger.info(f"スクリーンショットを Cloud Storage に保存: {url}")
            return url
        except Exception as e:
            logger.error(f"Cloud Storage 保存エラー: {e}")
            return None

    def save_dom_snapshot(
        self, trace_id: str, dom_html: str
    ) -> Optional[str]:
        """DOM スナップショットを Cloud Storage に保存"""
        if not self.client:
            logger.warning("Cloud Storage クライアントが利用不可です")
            return None

        try:
            bucket = self.client.bucket(self.bucket_name)
            blob_path = (
                f"{datetime.utcnow().strftime('%Y-%m-%d')}/{trace_id}/dom_snapshot.html"
            )
            blob = bucket.blob(blob_path)
            blob.upload_from_string(dom_html, content_type="text/html")
            url = f"gs://{self.bucket_name}/{blob_path}"
            logger.info(f"DOM スナップショットを Cloud Storage に保存: {url}")
            return url
        except Exception as e:
            logger.error(f"Cloud Storage 保存エラー: {e}")
            return None


class ErrorStorageManager:
    """ローカル/クラウド両対応のストレージマネージャー"""

    def __init__(self, use_cloud: bool = False):
        self.local_storage = LocalErrorStorage()
        self.cloud_storage = CloudErrorStorage() if use_cloud else None
        self.use_cloud = use_cloud and self.cloud_storage is not None

    def save_error_log(
        self, trace_id: str, error_log: Dict[str, Any]
    ) -> List[str]:
        """エラーログを保存（ローカルとクラウド）"""
        saved_paths = []

        # ローカルに保存
        local_path = self.local_storage.save_error_log(trace_id, error_log)
        if local_path:
            saved_paths.append(local_path)

        # クラウドに保存
        if self.use_cloud:
            cloud_path = self.cloud_storage.save_error_log(trace_id, error_log)
            if cloud_path:
                saved_paths.append(cloud_path)

        return saved_paths

    def save_screenshot(
        self, trace_id: str, step_name: str, screenshot_bytes: bytes
    ) -> List[str]:
        """スクリーンショットを保存（ローカルとクラウド）"""
        saved_paths = []

        # ローカルに保存
        local_path = self.local_storage.save_screenshot(trace_id, step_name, screenshot_bytes)
        if local_path:
            saved_paths.append(local_path)

        # クラウドに保存
        if self.use_cloud:
            cloud_path = self.cloud_storage.save_screenshot(trace_id, step_name, screenshot_bytes)
            if cloud_path:
                saved_paths.append(cloud_path)

        return saved_paths

    def save_dom_snapshot(
        self, trace_id: str, dom_html: str
    ) -> List[str]:
        """DOM スナップショットを保存（ローカルとクラウド）"""
        saved_paths = []

        # ローカルに保存
        local_path = self.local_storage.save_dom_snapshot(trace_id, dom_html)
        if local_path:
            saved_paths.append(local_path)

        # クラウドに保存
        if self.use_cloud:
            cloud_path = self.cloud_storage.save_dom_snapshot(trace_id, dom_html)
            if cloud_path:
                saved_paths.append(cloud_path)

        return saved_paths


# グローバルストレージマネージャー
# 本番環境では use_cloud=True に設定
error_storage_manager = ErrorStorageManager(use_cloud=os.getenv("GCP_PROJECT_ID") is not None)
