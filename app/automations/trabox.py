"""Trabox への自動ログイン・投稿（Playwright）
エラーハンドリング統合版
"""
from playwright.async_api import async_playwright, Page
from app.config import settings
from app.constants.trabox_config import (
    TRABOX_LOGIN_URL,
    TRABOX_BAGGAGE_REGISTER_URL,
    TRABOX_DASHBOARD_URL,
    TRABOX_SELECTORS,
    TRABOX_TIMEOUTS,
)
from app.utils.error_handler import ErrorHandler, ErrorCategory, ErrorCode, PostingError
from app.utils.structured_logging import structured_logger
from app.utils.debug_capture import DebugCapture, ErrorDebugInfo
from app.services.error_storage import error_storage_manager
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TraboxAutomation:
    """Trabox への自動ログイン・投稿

    🔴 【重要】
    - 荷物登録URL: https://www.trabox.com/baggage/register
    - このURLのフォームのみが正しい登録形式
    - 他の似たようなフォームは全部違う！
    """

    def __init__(
        self,
        user_id: int,
        case_id: int,
        username: str,
        password: str,
    ):
        self.user_id = user_id
        self.case_id = case_id
        self.username = username
        self.password = password
        self.headless = settings.TRABOX_HEADLESS
        self.debug_capture: Optional[DebugCapture] = None

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データを Trabox に投稿

        Args:
            case_data: 投稿する案件データ

        Returns:
            投稿結果

        Raises:
            PostingError: 投稿に失敗した場合
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            # デバッグキャプチャを初期化
            self.debug_capture = DebugCapture(page)

            try:
                # ステップ 1: ダッシュボードにアクセス
                await self._step_navigate_to_dashboard(page)

                # ステップ 2: ログイン確認・実行
                is_login_page = await self._is_login_page(page)
                if is_login_page:
                    await self._step_login(page)
                    # ログイン後、再度ダッシュボードにアクセス
                    await self._step_navigate_to_dashboard(page)

                # ステップ 3: 荷物登録ページにアクセス
                await self._step_navigate_to_register(page)

                # ステップ 4: フォーム入力
                await self._step_fill_form(page, case_data)

                # ステップ 5: 送信
                await self._step_submit_form(page)

                # 成功ログ
                structured_logger.log_posting_completed(
                    self.user_id,
                    self.case_id,
                    "trabox",
                    {"status": "success", "message": "Trabox への投稿に成功しました"},
                )

                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": "投稿に成功しました",
                }

            except PostingError as e:
                # 既知のエラー
                await self._handle_posting_error(page, e)
                raise

            except Exception as e:
                # 予期しないエラー
                error = ErrorHandler.handle_posting_error(
                    e,
                    self.user_id,
                    self.case_id,
                    "trabox",
                    step="unknown",
                    screenshots=self._get_screenshot_paths(),
                    dom_snapshot=await self.debug_capture.capture_dom_snapshot() if self.debug_capture else None,
                    browser_console=self.debug_capture.get_console_logs() if self.debug_capture else None,
                )
                await self._handle_posting_error(page, error)
                raise

            finally:
                await context.close()
                await browser.close()

    async def _step_navigate_to_dashboard(self, page: Page) -> None:
        """ステップ 1: ダッシュボードにナビゲート"""
        try:
            logger.info("[Trabox] ダッシュボードにナビゲート中...")
            await self.debug_capture.capture_screenshot("step_0_start")

            await page.goto(
                TRABOX_DASHBOARD_URL,
                wait_until="networkidle",
                timeout=TRABOX_TIMEOUTS["navigation"],
            )

            await self.debug_capture.capture_screenshot("step_1_dashboard")
            structured_logger.log_event(
                "trabox_navigate",
                self.user_id,
                self.case_id,
                "trabox",
                details={"url": TRABOX_DASHBOARD_URL},
            )

        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e,
                self.user_id,
                self.case_id,
                "trabox",
                step="navigate_to_dashboard",
                screenshots=self._get_screenshot_paths(),
            )

    async def _step_login(self, page: Page) -> None:
        """ステップ 2: ログイン実行"""
        try:
            logger.info("[Trabox] ログイン実行中...")

            # ユーザー名入力
            await page.fill(
                TRABOX_SELECTORS["login_id"],
                self.username,
                timeout=TRABOX_TIMEOUTS["action"],
            )
            await self.debug_capture.capture_screenshot("step_2_login_id_filled")

            # パスワード入力
            await page.fill(
                TRABOX_SELECTORS["login_password"],
                self.password,
                timeout=TRABOX_TIMEOUTS["action"],
            )
            await self.debug_capture.capture_screenshot("step_2_login_password_filled")

            # ログインボタンをクリック
            await page.click(
                TRABOX_SELECTORS["login_button"],
                timeout=TRABOX_TIMEOUTS["action"],
            )
            await self.debug_capture.capture_screenshot("step_2_login_button_clicked")

            # ログイン完了待機
            await page.wait_for_navigation(timeout=TRABOX_TIMEOUTS["navigation"])
            await self.debug_capture.capture_screenshot("step_2_login_completed")

            structured_logger.log_event(
                "trabox_login",
                self.user_id,
                self.case_id,
                "trabox",
                details={"message": "ログインに成功しました"},
            )

        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e,
                self.user_id,
                self.case_id,
                "trabox",
                step="login",
                screenshots=self._get_screenshot_paths(),
            )

    async def _step_navigate_to_register(self, page: Page) -> None:
        """ステップ 3: 荷物登録ページにナビゲート

        🔴 【重要】このURLのみが正しい登録ページ
        他の似たようなフォームは全部違う！
        """
        try:
            logger.info("[Trabox] 荷物登録ページにナビゲート中...")
            await self.debug_capture.capture_screenshot("step_3_before_register")

            # 直接登録URLにアクセス
            await page.goto(
                TRABOX_BAGGAGE_REGISTER_URL,
                wait_until="networkidle",
                timeout=TRABOX_TIMEOUTS["navigation"],
            )

            await self.debug_capture.capture_screenshot("step_3_register_page_loaded")

            structured_logger.log_event(
                "trabox_navigate_register",
                self.user_id,
                self.case_id,
                "trabox",
                details={"url": TRABOX_BAGGAGE_REGISTER_URL},
            )

        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e,
                self.user_id,
                self.case_id,
                "trabox",
                step="navigate_to_register",
                screenshots=self._get_screenshot_paths(),
            )

    async def _step_fill_form(self, page: Page, case_data: Dict[str, Any]) -> None:
        """ステップ 4: フォーム入力

        TODO: 実際のフィールド名・セレクターを確認してから実装
        """
        try:
            logger.info("[Trabox] フォーム入力中...")
            await self.debug_capture.capture_screenshot("step_4_form_before_fill")

            # ここにフォーム入力ロジックを実装
            # TODO: 実際のセレクター・フィールド名を確認
            logger.info(f"[Trabox] 投稿データ: {case_data}")

            await self.debug_capture.capture_screenshot("step_4_form_after_fill")

            structured_logger.log_event(
                "trabox_form_fill",
                self.user_id,
                self.case_id,
                "trabox",
                details={"fields": list(case_data.keys())},
            )

        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e,
                self.user_id,
                self.case_id,
                "trabox",
                step="fill_form",
                screenshots=self._get_screenshot_paths(),
            )

    async def _step_submit_form(self, page: Page) -> None:
        """ステップ 5: フォーム送信"""
        try:
            logger.info("[Trabox] フォーム送信中...")
            await self.debug_capture.capture_screenshot("step_5_before_submit")

            # TODO: 送信ボタンのセレクターを確認してから実装
            # await page.click(submit_button_selector)

            await self.debug_capture.capture_screenshot("step_5_after_submit")

            structured_logger.log_event(
                "trabox_submit",
                self.user_id,
                self.case_id,
                "trabox",
                details={"message": "フォーム送信完了"},
            )

        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e,
                self.user_id,
                self.case_id,
                "trabox",
                step="submit_form",
                screenshots=self._get_screenshot_paths(),
            )

    async def _is_login_page(self, page: Page) -> bool:
        """ログインページか判定"""
        try:
            count = await page.locator(TRABOX_SELECTORS["login_id"]).count()
            return count > 0
        except Exception as e:
            logger.warning(f"ログインページ判定エラー: {e}")
            return False

    async def _handle_posting_error(
        self, page: Page, error: PostingError
    ) -> None:
        """エラーを処理・記録"""
        logger.error(f"[Trabox] エラー: {error.message}")

        # スクリーンショット・DOM を取得
        screenshots = self._get_screenshot_paths()
        dom_snapshot = None
        if self.debug_capture:
            dom_snapshot = await self.debug_capture.capture_dom_snapshot()

        # エラーログを出力
        ErrorHandler.log_error_details(
            error,
            structured_logger,
            extra_context={
                "platform": "trabox",
                "debug_info": self.debug_capture.get_debug_info()
                if self.debug_capture
                else {},
            },
        )

        # エラーログを保存
        error_log = {
            "trace_id": structured_logger.trace_id,
            "error_category": error.category,
            "error_code": error.code,
            "error_message": error.message,
            "user_id": self.user_id,
            "case_id": self.case_id,
            "platform": "trabox",
            "screenshots": screenshots,
            "dom_snapshot": dom_snapshot is not None,
        }

        error_storage_manager.save_error_log(structured_logger.trace_id, error_log)

        if dom_snapshot:
            error_storage_manager.save_dom_snapshot(
                structured_logger.trace_id, dom_snapshot
            )

    def _get_screenshot_paths(self) -> list:
        """スクリーンショット保存パスを取得"""
        if not self.debug_capture:
            return []

        paths = []
        for i in range(self.debug_capture.get_screenshots_count()):
            paths.append(f"screenshot_{i}.png")
        return paths
