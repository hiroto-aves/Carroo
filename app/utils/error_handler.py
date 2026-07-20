"""エラーハンドリング統一ロジック"""
import traceback
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """エラーカテゴリー"""

    AUTH = "AUTH"  # 認証情報エラー
    SELECTOR = "SELECTOR"  # 要素見つからない
    TIMEOUT = "TIMEOUT"  # タイムアウト
    NETWORK = "NETWORK"  # ネットワークエラー
    UNEXPECTED = "UNEXPECTED"  # 予期しないエラー
    CONFIG = "CONFIG"  # 設定エラー


class ErrorCode(str, Enum):
    """エラーコード"""

    # 認証エラー
    AUTH_CREDENTIALS_MISSING = "AUTH_CREDENTIALS_MISSING"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"

    # セレクターエラー
    SELECTOR_NOT_FOUND = "SELECTOR_NOT_FOUND"
    ELEMENT_NOT_VISIBLE = "ELEMENT_NOT_VISIBLE"
    ELEMENT_DISABLED = "ELEMENT_DISABLED"

    # タイムアウトエラー
    TIMEOUT_NAVIGATION = "TIMEOUT_NAVIGATION"
    TIMEOUT_SELECTOR = "TIMEOUT_SELECTOR"
    TIMEOUT_ACTION = "TIMEOUT_ACTION"

    # ネットワークエラー
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_CONNECTION_REFUSED = "NETWORK_CONNECTION_REFUSED"
    NETWORK_DNS_FAILED = "NETWORK_DNS_FAILED"

    # 設定エラー
    CONFIG_MISSING_CREDENTIALS = "CONFIG_MISSING_CREDENTIALS"
    CONFIG_INVALID_CREDENTIALS = "CONFIG_INVALID_CREDENTIALS"

    # 予期しないエラー
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class PostingError(Exception):
    """投稿処理用のカスタムエラークラス"""

    def __init__(
        self,
        category: ErrorCategory,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.category = category
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ErrorHandler:
    """エラー処理の統一ロジック"""

    @staticmethod
    def categorize_error(exception: Exception) -> tuple[ErrorCategory, ErrorCode, str]:
        """例外をカテゴリー・コード・メッセージに分類"""
        error_message = str(exception)
        exception_type = type(exception).__name__

        # タイムアウトエラー
        if "Timeout" in exception_type or "timeout" in error_message.lower():
            if "navigation" in error_message.lower():
                return (
                    ErrorCategory.TIMEOUT,
                    ErrorCode.TIMEOUT_NAVIGATION,
                    f"ページナビゲーションのタイムアウト: {error_message}",
                )
            elif "selector" in error_message.lower():
                return (
                    ErrorCategory.TIMEOUT,
                    ErrorCode.TIMEOUT_SELECTOR,
                    f"セレクター待機のタイムアウト: {error_message}",
                )
            else:
                return (
                    ErrorCategory.TIMEOUT,
                    ErrorCode.TIMEOUT_ACTION,
                    f"アクションのタイムアウト: {error_message}",
                )

        # セレクターエラー
        if "not found" in error_message.lower() or "selector" in error_message.lower():
            return (
                ErrorCategory.SELECTOR,
                ErrorCode.SELECTOR_NOT_FOUND,
                f"要素が見つかりません: {error_message}",
            )

        if "not visible" in error_message.lower():
            return (
                ErrorCategory.SELECTOR,
                ErrorCode.ELEMENT_NOT_VISIBLE,
                f"要素が表示されていません: {error_message}",
            )

        if "disabled" in error_message.lower():
            return (
                ErrorCategory.SELECTOR,
                ErrorCode.ELEMENT_DISABLED,
                f"要素が無効です: {error_message}",
            )

        # ネットワークエラー
        if "connection" in error_message.lower() or "refused" in error_message.lower():
            return (
                ErrorCategory.NETWORK,
                ErrorCode.NETWORK_CONNECTION_REFUSED,
                f"接続が拒否されました: {error_message}",
            )

        if "dns" in error_message.lower():
            return (
                ErrorCategory.NETWORK,
                ErrorCode.NETWORK_DNS_FAILED,
                f"DNS 解決に失敗しました: {error_message}",
            )

        # デフォルト
        return (
            ErrorCategory.UNEXPECTED,
            ErrorCode.UNEXPECTED_ERROR,
            f"予期しないエラーが発生しました: {error_message}",
        )

    @staticmethod
    def create_error_context(
        exception: Exception,
        user_id: Optional[int] = None,
        case_id: Optional[int] = None,
        platform: Optional[str] = None,
        step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """エラーコンテキストを作成"""
        category, code, message = ErrorHandler.categorize_error(exception)

        return {
            "error_category": category,
            "error_code": code,
            "error_message": message,
            "exception_type": type(exception).__name__,
            "stack_trace": traceback.format_exc(),
            "user_id": user_id,
            "case_id": case_id,
            "platform": platform,
            "step": step,
            "original_message": str(exception),
        }

    @staticmethod
    def handle_posting_error(
        exception: Exception,
        user_id: int,
        case_id: int,
        platform: str,
        step: Optional[str] = None,
        screenshots: Optional[List[str]] = None,
        dom_snapshot: Optional[str] = None,
        browser_console: Optional[List[Dict[str, Any]]] = None,
    ) -> PostingError:
        """投稿エラーを処理"""
        context = ErrorHandler.create_error_context(
            exception,
            user_id=user_id,
            case_id=case_id,
            platform=platform,
            step=step,
        )

        error = PostingError(
            category=context["error_category"],
            code=context["error_code"],
            message=context["error_message"],
            details={
                "exception_type": context["exception_type"],
                "stack_trace": context["stack_trace"],
                "step": step,
                "screenshots": screenshots or [],
                "dom_snapshot": dom_snapshot,
                "browser_console": browser_console or [],
                "original_message": context["original_message"],
            },
        )

        return error

    @staticmethod
    def log_error_details(
        error: PostingError,
        structured_logger,
        extra_context: Optional[Dict[str, Any]] = None,
    ):
        """エラー詳細をログ出力"""
        screenshots = error.details.get("screenshots", [])
        dom = error.details.get("dom_snapshot")
        console = error.details.get("browser_console", [])

        structured_logger.log_error(
            error_category=error.category,
            error_message=error.message,
            error_code=error.code,
            stack_trace=error.details.get("stack_trace"),
            screenshots=screenshots,
            dom_snapshot=dom,
            browser_console=console if console else None,
            extra_context=extra_context,
        )
