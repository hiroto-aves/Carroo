from playwright.async_api import async_playwright
from app.config import settings
from typing import Dict, Any

class TraboxAutomation:
    """トラボックスへの自動ログイン・投稿を実行"""

    def __init__(self):
        self.url = settings.TRABOX_URL
        self.headless = settings.TRABOX_HEADLESS

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データをトラボックスに投稿"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()

            try:
                await page.goto(self.url)

                await page.fill('input[name="loginid"]', case_data.get("username"))
                await page.fill('input[name="loginpwd"]', case_data.get("password"))

                login_button = page.locator('button:has-text("ログイン")')
                await login_button.click()

                await page.wait_for_navigation()

                await self._fill_form(page, case_data)

                submit_button = page.locator('button:has-text("送信")')
                await submit_button.click()

                await page.wait_for_navigation()

                await page.screenshot(path="success_trabox.png")

                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": "Case posted to Trabox successfully"
                }

            except Exception as e:
                await page.screenshot(path="error_screenshot.png")
                return {
                    "status": "error",
                    "platform": "trabox",
                    "message": str(e)
                }

            finally:
                await browser.close()

    async def _fill_form(self, page, case_data: Dict[str, Any]):
        """フォームにデータを入力"""
        try:
            await page.fill('input[placeholder="積地"]', case_data.get("pick_location", ""))
            await page.fill('input[placeholder="卸地"]', case_data.get("drop_location", ""))
            await page.fill('input[type="number"]', str(case_data.get("cargo_weight", "")))
            await page.select_option('select', case_data.get("vehicle_type", ""))
            await page.fill('input[type="date"]', case_data.get("pickup_date", ""))

        except Exception as e:
            print(f"Error filling form: {e}")
            raise
