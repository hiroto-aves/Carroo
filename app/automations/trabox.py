from playwright.async_api import async_playwright, TimeoutError, Page
from app.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TraboxAutomation:
    """トラボックスへの自動ログイン・投稿を実行（Playwright）

    既知情報：
    - ログイン画面：input[name="loginid"], input[name="loginpwd"]
    - ログインボタン：span タグで「ログイン」テキスト
    """

    def __init__(self):
        self.url = settings.TRABOX_URL
        self.headless = settings.TRABOX_HEADLESS
        self.timeout = 30000
        self.navigation_timeout = 10000

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データをトラボックスに投稿"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            page.set_default_timeout(self.timeout)
            page.set_default_navigation_timeout(self.navigation_timeout)

            try:
                logger.info(f"[Trabox] Accessing {self.url}")
                await page.goto(self.url, wait_until="domcontentloaded")

                logger.info("[Trabox] Logging in...")
                await self._login(page, case_data)

                logger.info("[Trabox] Filling form...")
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
                try:
                    await page.screenshot(path="error_screenshot_trabox_timeout.png")
                except:
                    pass
                return {
                    "status": "error",
                    "platform": "trabox",
                    "message": f"Timeout during operation: {str(e)}"
                }

            except Exception as e:
                logger.error(f"[Trabox] Error: {type(e).__name__}: {e}")
                try:
                    await page.screenshot(path="error_screenshot_trabox.png")
                except:
                    pass
                return {
                    "status": "error",
                    "platform": "trabox",
                    "message": f"{type(e).__name__}: {str(e)}"
                }

            finally:
                await context.close()
                await browser.close()

    async def _login(self, page: Page, case_data: Dict[str, Any]):
        """トラボックスにログイン

        要素：
        - ID入力: input[name="loginid"]
        - PW入力: input[name="loginpwd"]
        - ログインボタン: span:has-text("ログイン") または button:has-text("ログイン")
        """
        username = case_data.get("username")
        password = case_data.get("password")

        if not username or not password:
            raise ValueError("Username and password required for Trabox login")

        # ID入力
        logger.debug(f"[Trabox] Filling login ID")
        login_id = page.locator('input[name="loginid"]')
        await login_id.fill(username)

        # パスワード入力
        logger.debug(f"[Trabox] Filling login password")
        login_pwd = page.locator('input[name="loginpwd"]')
        await login_pwd.fill(password)

        # ログインボタンクリック
        logger.debug(f"[Trabox] Clicking login button")
        login_button = page.locator('span:has-text("ログイン")')
        if await login_button.count() > 0:
            await login_button.click()
        else:
            login_button_alt = page.locator('button:has-text("ログイン")')
            await login_button_alt.click()

        # ナビゲーション完了待機
        try:
            await page.wait_for_navigation(wait_until="domcontentloaded")
        except:
            # ナビゲーションが発生しない場合もあるため、要素の出現を待つ
            await page.wait_for_selector('body', timeout=5000)

        logger.info("[Trabox] Login completed")

    async def _fill_and_submit_form(self, page: Page, case_data: Dict[str, Any]):
        """案件フォームを入力して送信"""
        pick_location = case_data.get("pick_location", "")
        drop_location = case_data.get("drop_location", "")
        cargo_weight = str(case_data.get("cargo_weight", ""))
        vehicle_type = case_data.get("vehicle_type", "")
        freight_rate = str(case_data.get("freight_rate", ""))
        pickup_date = case_data.get("pickup_date", "")
        pickup_time = case_data.get("pickup_time", "")

        # 積地入力
        logger.debug(f"[Trabox] Filling pick_location: {pick_location}")
        pick_input = page.locator('input[placeholder*="積地"], input[name*="pick"], input[id*="pick"]')
        if await pick_input.count() > 0:
            await pick_input.first.fill(pick_location)
        else:
            logger.warning("[Trabox] Could not find pick_location input")

        # 卸地入力
        logger.debug(f"[Trabox] Filling drop_location: {drop_location}")
        drop_input = page.locator('input[placeholder*="卸地"], input[name*="drop"], input[id*="drop"]')
        if await drop_input.count() > 0:
            await drop_input.first.fill(drop_location)
        else:
            logger.warning("[Trabox] Could not find drop_location input")

        # 重量入力
        if cargo_weight:
            logger.debug(f"[Trabox] Filling cargo_weight: {cargo_weight}")
            weight_inputs = page.locator('input[type="number"], input[id*="weight"], input[name*="weight"]')
            if await weight_inputs.count() > 0:
                await weight_inputs.first.fill(cargo_weight)

        # 日付入力
        if pickup_date:
            logger.debug(f"[Trabox] Filling pickup_date: {pickup_date}")
            date_inputs = page.locator('input[type="date"], input[id*="date"], input[name*="date"]')
            if await date_inputs.count() > 0:
                await date_inputs.first.fill(pickup_date)

        # 時間入力
        if pickup_time:
            logger.debug(f"[Trabox] Filling pickup_time: {pickup_time}")
            time_inputs = page.locator('input[type="time"], input[id*="time"]')
            if await time_inputs.count() > 0:
                await time_inputs.first.fill(pickup_time)

        # 車種選択
        if vehicle_type:
            logger.debug(f"[Trabox] Selecting vehicle_type: {vehicle_type}")
            selects = page.locator('select')
            if await selects.count() > 0:
                try:
                    await selects.first.select_option(vehicle_type)
                except:
                    logger.warning(f"[Trabox] Could not select vehicle_type: {vehicle_type}")

        # 運賃入力
        if freight_rate:
            logger.debug(f"[Trabox] Filling freight_rate: {freight_rate}")
            rate_inputs = page.locator('input[id*="rate"], input[id*="price"], input[id*="fare"]')
            if await rate_inputs.count() > 0:
                await rate_inputs.first.fill(freight_rate)

        # 送信
        logger.debug(f"[Trabox] Clicking submit button")
        submit_button = page.locator('button:has-text("送信"), button:has-text("登録"), button:has-text("投稿")')
        if await submit_button.count() > 0:
            await submit_button.click()
        else:
            logger.error("[Trabox] Could not find submit button")
            raise Exception("Submit button not found")

        # 送信完了待機
        try:
            await page.wait_for_navigation(wait_until="domcontentloaded")
        except:
            await page.wait_for_selector('body', timeout=5000)

        logger.info("[Trabox] Form submitted successfully")
