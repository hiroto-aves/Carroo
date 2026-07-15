from playwright.async_api import async_playwright, TimeoutError
from app.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TraboxAutomation:
    """トラボックスへの自動ログイン・投稿を実行（Playwright）"""

    def __init__(self):
        self.url = settings.TRABOX_URL
        self.headless = settings.TRABOX_HEADLESS
        self.timeout = 30000

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データをトラボックスに投稿"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                logger.info(f"[Trabox] Accessing {self.url}")
                await page.goto(self.url, wait_until="networkidle", timeout=self.timeout)

                await self._login(page, case_data)
                await self._fill_and_submit_form(page, case_data)

                await page.screenshot(path="success_trabox.png")
                logger.info("[Trabox] Case posted successfully")

                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": "Case posted to Trabox successfully"
                }

            except TimeoutError as e:
                logger.error(f"[Trabox] Timeout: {e}")
                await page.screenshot(path="error_screenshot_trabox.png")
                return {
                    "status": "error",
                    "platform": "trabox",
                    "message": f"Timeout: {str(e)}"
                }

            except Exception as e:
                logger.error(f"[Trabox] Error: {e}")
                await page.screenshot(path="error_screenshot_trabox.png")
                return {
                    "status": "error",
                    "platform": "trabox",
                    "message": str(e)
                }

            finally:
                await context.close()
                await browser.close()

    async def _login(self, page, case_data: Dict[str, Any]):
        """トラボックスにログイン"""
        logger.info("[Trabox] Attempting login...")

        username = case_data.get("username")
        password = case_data.get("password")

        if not username or not password:
            raise ValueError("Username and password required for Trabox")

        try:
            login_id_input = page.locator('input[name="loginid"]')
            login_pwd_input = page.locator('input[name="loginpwd"]')

            await login_id_input.fill(username, timeout=self.timeout)
            await login_pwd_input.fill(password, timeout=self.timeout)

            login_button = page.locator('button:has-text("ログイン"), span:has-text("ログイン")')
            await login_button.click(timeout=self.timeout)

            await page.wait_for_navigation(wait_until="networkidle", timeout=self.timeout)
            logger.info("[Trabox] Login successful")

        except TimeoutError as e:
            raise TimeoutError(f"Trabox login timeout: {e}")
        except Exception as e:
            await page.screenshot(path="trabox_login_error.png")
            raise Exception(f"Trabox login failed: {e}")

    async def _fill_and_submit_form(self, page, case_data: Dict[str, Any]):
        """案件フォームを入力して送信"""
        logger.info("[Trabox] Filling form...")

        try:
            pick_location = case_data.get("pick_location", "")
            drop_location = case_data.get("drop_location", "")
            cargo_weight = case_data.get("cargo_weight", "")
            vehicle_type = case_data.get("vehicle_type", "")
            freight_rate = case_data.get("freight_rate", "")
            pickup_date = case_data.get("pickup_date", "")

            await page.locator('input[placeholder*="積地"], input[name*="pick"]').fill(
                pick_location, timeout=self.timeout
            )
            await page.locator('input[placeholder*="卸地"], input[name*="drop"]').fill(
                drop_location, timeout=self.timeout
            )

            weight_input = page.locator('input[type="number"]')
            if await weight_input.count() > 0:
                await weight_input.first.fill(str(cargo_weight), timeout=self.timeout)

            date_input = page.locator('input[type="date"]')
            if await date_input.count() > 0:
                await date_input.first.fill(pickup_date, timeout=self.timeout)

            vehicle_select = page.locator('select')
            if await vehicle_select.count() > 0:
                await vehicle_select.first.select_option(vehicle_type, timeout=self.timeout)

            logger.info("[Trabox] Form filled, submitting...")
            submit_button = page.locator('button:has-text("送信"), button:has-text("登録")')
            await submit_button.click(timeout=self.timeout)

            await page.wait_for_navigation(wait_until="networkidle", timeout=self.timeout)

        except Exception as e:
            await page.screenshot(path="trabox_form_error.png")
            raise Exception(f"Form submission failed: {e}")
