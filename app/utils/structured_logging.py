"""構造化ログ出力（JSON）"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from app.config import settings

logger = logging.getLogger(__name__)


class StructuredLogger:
    """JSON 形式の構造化ログを出力"""

    def __init__(self):
        self.trace_id = str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())

    def log_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        case_id: Optional[int] = None,
        platform: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
    ) -> Dict[str, Any]:
        """イベントをログ出力"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "event_type": event_type,
            "level": level,
            "user_id": user_id,
            "case_id": case_id,
            "platform": platform,
            "details": details or {},
        }

        # ログレベルに応じて出力
        if level == "ERROR":
            logger.error(json.dumps(log_entry, ensure_ascii=False))
        elif level == "WARNING":
            logger.warning(json.dumps(log_entry, ensure_ascii=False))
        else:
            logger.info(json.dumps(log_entry, ensure_ascii=False))

        return log_entry

    def log_error(
        self,
        error_category: str,
        error_message: str,
        error_code: str,
        user_id: Optional[int] = None,
        case_id: Optional[int] = None,
        platform: Optional[str] = None,
        stack_trace: Optional[str] = None,
        screenshots: Optional[List[str]] = None,
        dom_snapshot: Optional[str] = None,
        browser_console: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """エラーをログ出力（詳細情報付き）"""
        error_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "level": "ERROR",
            "error_category": error_category,
            "error_message": error_message,
            "error_code": error_code,
            "user_id": user_id,
            "case_id": case_id,
            "platform": platform,
            "stack_trace": stack_trace,
            "screenshots": screenshots or [],
            "dom_snapshot": dom_snapshot,
            "browser_console": browser_console or [],
            "extra_context": extra_context or {},
        }

        logger.error(json.dumps(error_entry, ensure_ascii=False, indent=2))
        return error_entry

    def log_posting_started(
        self, user_id: int, case_id: int, platform: str
    ) -> Dict[str, Any]:
        """投稿開始をログ出力"""
        return self.log_event(
            event_type="posting_started",
            user_id=user_id,
            case_id=case_id,
            platform=platform,
            details={
                "message": f"{platform} への投稿を開始しました",
            },
        )

    def log_posting_completed(
        self, user_id: int, case_id: int, platform: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """投稿完了をログ出力"""
        return self.log_event(
            event_type="posting_completed",
            user_id=user_id,
            case_id=case_id,
            platform=platform,
            details={
                "message": f"{platform} への投稿が完了しました",
                "result": result,
            },
        )

    def log_posting_failed(
        self,
        user_id: int,
        case_id: int,
        platform: str,
        error_category: str,
        error_message: str,
        error_code: str,
        stack_trace: Optional[str] = None,
        screenshots: Optional[List[str]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """投稿失敗をログ出力"""
        return self.log_error(
            error_category=error_category,
            error_message=error_message,
            error_code=error_code,
            user_id=user_id,
            case_id=case_id,
            platform=platform,
            stack_trace=stack_trace,
            screenshots=screenshots,
            extra_context={
                **{"message": f"{platform} への投稿に失敗しました"},
                **(extra_context or {}),
            },
        )


# グローバルロガーインスタンス
structured_logger = StructuredLogger()
