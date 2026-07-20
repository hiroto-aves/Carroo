"""ブラウザのデバッグ情報を取得・保存"""
import asyncio
from typing import Optional, List, Dict, Any
from playwright.async_api import Page, Browser
import logging

logger = logging.getLogger(__name__)


class DebugCapture:
    """Playwright ページからデバッグ情報をキャプチャ"""

    def __init__(self, page: Page):
        self.page = page
        self.console_logs: List[Dict[str, Any]] = []
        self.network_logs: List[Dict[str, Any]] = []
        self.page_errors: List[str] = []
        self.screenshots: List[bytes] = []

        # イベントリスナーを設定
        self._setup_listeners()

    def _setup_listeners(self):
        """ページイベントリスナーを設定"""
        try:
            self.page.on("console", self._on_console_message)
            self.page.on("pageerror", self._on_page_error)
        except Exception as e:
            logger.warning(f"リスナー設定エラー: {e}")

    def _on_console_message(self, msg):
        """コンソールメッセージをキャプチャ"""
        try:
            self.console_logs.append(
                {
                    "type": msg.type,
                    "text": msg.text,
                    "location": str(msg.location) if msg.location else None,
                }
            )
        except Exception as e:
            logger.debug(f"コンソールログキャプチャエラー: {e}")

    def _on_page_error(self, exc):
        """ページエラーをキャプチャ"""
        try:
            self.page_errors.append(str(exc))
        except Exception as e:
            logger.debug(f"ページエラーキャプチャエラー: {e}")

    async def capture_screenshot(self, step_name: str) -> Optional[bytes]:
        """スクリーンショットを撮影"""
        try:
            screenshot = await self.page.screenshot()
            self.screenshots.append(screenshot)
            logger.debug(f"スクリーンショット撮影: {step_name}")
            return screenshot
        except Exception as e:
            logger.warning(f"スクリーンショット撮影エラー: {e}")
            return None

    async def capture_dom_snapshot(self) -> Optional[str]:
        """DOM スナップショットを取得"""
        try:
            dom_html = await self.page.content()
            logger.debug(f"DOM スナップショット取得: {len(dom_html)} bytes")
            return dom_html
        except Exception as e:
            logger.warning(f"DOM スナップショット取得エラー: {e}")
            return None

    async def capture_page_state(self) -> Dict[str, Any]:
        """ページ状態をキャプチャ"""
        try:
            return {
                "url": self.page.url,
                "title": await self.page.title(),
                "viewport": self.page.viewportSize,
            }
        except Exception as e:
            logger.warning(f"ページ状態キャプチャエラー: {e}")
            return {}

    def get_console_logs(self) -> List[Dict[str, Any]]:
        """コンソールログを取得"""
        return self.console_logs

    def get_page_errors(self) -> List[str]:
        """ページエラーを取得"""
        return self.page_errors

    def get_screenshots_count(self) -> int:
        """スクリーンショット枚数を取得"""
        return len(self.screenshots)

    async def capture_full_debug_info(self, step_name: str) -> Dict[str, Any]:
        """全デバッグ情報をキャプチャ"""
        screenshot = await self.capture_screenshot(step_name)
        dom = await self.capture_dom_snapshot()
        page_state = await self.capture_page_state()

        return {
            "step": step_name,
            "page_state": page_state,
            "screenshot_captured": screenshot is not None,
            "dom_captured": dom is not None,
            "console_logs": self.get_console_logs(),
            "page_errors": self.get_page_errors(),
        }


class ErrorDebugInfo:
    """エラー時のデバッグ情報をまとめる"""

    def __init__(self, capture: DebugCapture):
        self.capture = capture

    def get_debug_info(self) -> Dict[str, Any]:
        """デバッグ情報を辞書形式で取得"""
        return {
            "screenshots_count": self.capture.get_screenshots_count(),
            "console_logs": self.capture.get_console_logs(),
            "page_errors": self.capture.get_page_errors(),
            "console_summary": self._summarize_console_logs(),
            "error_summary": self._summarize_page_errors(),
        }

    def _summarize_console_logs(self) -> str:
        """コンソールログをサマリー"""
        logs = self.capture.get_console_logs()
        if not logs:
            return "コンソールログなし"

        error_count = sum(1 for log in logs if log["type"] == "error")
        warning_count = sum(1 for log in logs if log["type"] == "warning")
        return f"エラー: {error_count}, 警告: {warning_count}, 合計: {len(logs)}"

    def _summarize_page_errors(self) -> str:
        """ページエラーをサマリー"""
        errors = self.capture.get_page_errors()
        if not errors:
            return "ページエラーなし"
        return f"{len(errors)} 件のエラー\n" + "\n".join(errors[:3])
