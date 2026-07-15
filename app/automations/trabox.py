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
                # ダッシュボードにアクセス
                dashboard_url = f"{self.url}/baggage/list/opened"
                logger.info(f"[Trabox] Accessing dashboard: {dashboard_url}")
                await page.goto(dashboard_url, wait_until="networkidle")

                # ログインが必要か確認
                is_login_page = await page.locator('input[name="loginid"]').count() > 0
                if is_login_page:
                    logger.info("[Trabox] Login page detected, logging in...")
                    await self._login(page, case_data)
                    # ログイン後、再度ダッシュボードにアクセス
                    await page.goto(dashboard_url, wait_until="networkidle")

                # ダッシュボード上で「新規投稿」ボタンを探して押す
                logger.info("[Trabox] Looking for posting button...")
                posting_button_selectors = [
                    'a:has-text("新規登録")',
                    'button:has-text("新規登録")',
                    'a:has-text("追加")',
                    'button:has-text("追加")',
                    'a[href*="register"]',
                    'button[href*="register"]'
                ]

                button_clicked = False
                for selector in posting_button_selectors:
                    button = page.locator(selector)
                    if await button.count() > 0:
                        try:
                            await button.first.click()
                            logger.info(f"[Trabox] Clicked posting button with selector: {selector}")
                            button_clicked = True
                            await page.wait_for_timeout(2000)  # フォーム読み込み待機
                            break
                        except Exception as e:
                            logger.debug(f"[Trabox] Failed to click button ({selector}): {e}")
                            continue

                if not button_clicked:
                    # ボタンが見つからない場合、直接フォームページにアクセス
                    logger.warning("[Trabox] Posting button not found, navigating directly to form page")
                    await page.goto(f"{self.url}/baggage/register", wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)

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
        """案件フォームを入力して送信

        トラボックスのフォーム要素は動的にレンダリングされるため、
        複数のセレクター戦略を試して対応します
        """
        pick_location = case_data.get("pick_location", "")
        drop_location = case_data.get("drop_location", "")
        cargo_weight = str(case_data.get("cargo_weight", ""))
        vehicle_type = case_data.get("vehicle_type", "")
        freight_rate = str(case_data.get("freight_rate", ""))
        pickup_date = case_data.get("pickup_date", "")
        pickup_time = case_data.get("pickup_time", "")
        contact_name = case_data.get("contact_name", "")
        contact_phone = case_data.get("contact_phone", "")
        contact_email = case_data.get("contact_email", "")

        # ページが完全に読み込まれるまで待機
        await page.wait_for_timeout(1500)

        # デバッグ用スクリーンショット
        try:
            await page.screenshot(path="trabox_form_before.png")
        except:
            pass

        # 積地入力
        if pick_location:
            logger.debug(f"[Trabox] Filling pick_location: {pick_location}")
            # セレクター優先度: name → id → placeholder
            selectors = [
                'input[name*="pick"]',
                'input[id*="pick"]',
                'input[placeholder*="積地"]',
                'input[placeholder*="出発地"]',
                'textarea[name*="pick"]'
            ]
            filled = await self._fill_field(page, selectors, pick_location, "pick_location")
            if not filled:
                logger.warning("[Trabox] Could not find pick_location input")

        # 卸地入力
        if drop_location:
            logger.debug(f"[Trabox] Filling drop_location: {drop_location}")
            selectors = [
                'input[name*="drop"]',
                'input[id*="drop"]',
                'input[placeholder*="卸地"]',
                'input[placeholder*="到着地"]',
                'textarea[name*="drop"]'
            ]
            filled = await self._fill_field(page, selectors, drop_location, "drop_location")
            if not filled:
                logger.warning("[Trabox] Could not find drop_location input")

        # 重量入力
        if cargo_weight:
            logger.debug(f"[Trabox] Filling cargo_weight: {cargo_weight}")
            selectors = [
                'input[name*="weight"]',
                'input[id*="weight"]',
                'input[type="number"]',
                'input[placeholder*="重量"]'
            ]
            await self._fill_field(page, selectors, cargo_weight, "cargo_weight")

        # 日付入力
        if pickup_date:
            logger.debug(f"[Trabox] Filling pickup_date: {pickup_date}")
            selectors = [
                'input[name*="date"]',
                'input[id*="date"]',
                'input[type="date"]',
                'input[placeholder*="日付"]'
            ]
            await self._fill_field(page, selectors, pickup_date, "pickup_date")

        # 時間入力
        if pickup_time:
            logger.debug(f"[Trabox] Filling pickup_time: {pickup_time}")
            selectors = [
                'input[name*="time"]',
                'input[id*="time"]',
                'input[type="time"]',
                'input[placeholder*="時間"]'
            ]
            await self._fill_field(page, selectors, pickup_time, "pickup_time")

        # 車種選択
        if vehicle_type:
            logger.debug(f"[Trabox] Selecting vehicle_type: {vehicle_type}")
            selects = page.locator('select')
            select_count = await selects.count()
            if select_count > 0:
                try:
                    await selects.first.select_option(vehicle_type)
                except Exception as e:
                    logger.warning(f"[Trabox] Could not select vehicle_type: {e}")

        # 運賃入力
        if freight_rate:
            logger.debug(f"[Trabox] Filling freight_rate: {freight_rate}")
            selectors = [
                'input[name*="rate"]',
                'input[name*="price"]',
                'input[name*="fare"]',
                'input[id*="rate"]',
                'input[id*="price"]',
                'input[placeholder*="運賃"]'
            ]
            await self._fill_field(page, selectors, freight_rate, "freight_rate")

        # 連絡先名入力
        if contact_name:
            logger.debug(f"[Trabox] Filling contact_name: {contact_name}")
            selectors = [
                'input[name*="name"]',
                'input[id*="name"]',
                'input[placeholder*="名前"]',
                'input[placeholder*="担当者"]'
            ]
            await self._fill_field(page, selectors, contact_name, "contact_name")

        # 電話番号入力
        if contact_phone:
            logger.debug(f"[Trabox] Filling contact_phone: {contact_phone}")
            selectors = [
                'input[name*="phone"]',
                'input[type="tel"]',
                'input[id*="phone"]',
                'input[placeholder*="電話"]'
            ]
            await self._fill_field(page, selectors, contact_phone, "contact_phone")

        # メールアドレス入力
        if contact_email:
            logger.debug(f"[Trabox] Filling contact_email: {contact_email}")
            selectors = [
                'input[name*="email"]',
                'input[type="email"]',
                'input[id*="email"]',
                'input[placeholder*="メール"]'
            ]
            await self._fill_field(page, selectors, contact_email, "contact_email")

        # デバッグ用スクリーンショット
        try:
            await page.screenshot(path="trabox_form_filled.png")
        except:
            pass

        # 送信ボタン探索
        logger.debug(f"[Trabox] Clicking submit button")
        submit_selectors = [
            'button:has-text("登録")',
            'button:has-text("送信")',
            'button:has-text("投稿")',
            'input[type="submit"]',
            'button[type="submit"]'
        ]

        submitted = False
        for selector in submit_selectors:
            button = page.locator(selector)
            if await button.count() > 0:
                try:
                    await button.first.click()
                    logger.info(f"[Trabox] Submitted with selector: {selector}")
                    submitted = True
                    break
                except Exception as e:
                    logger.warning(f"[Trabox] Could not click submit button ({selector}): {e}")
                    continue

        if not submitted:
            logger.error("[Trabox] Could not find or click submit button")
            raise Exception("Submit button not found")

        # 送信完了待機
        try:
            await page.wait_for_navigation(wait_until="domcontentloaded", timeout=10000)
        except:
            await page.wait_for_timeout(3000)

        logger.info("[Trabox] Form submitted successfully")

    async def _fill_field(self, page: Page, selectors: list, value: str, field_name: str) -> bool:
        """複数のセレクターを試して、フィールドに値を入力する"""
        for selector in selectors:
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    await locator.first.fill(value)
                    logger.debug(f"[Trabox] Filled {field_name} with selector: {selector}")
                    return True
            except Exception as e:
                logger.debug(f"[Trabox] Failed to fill {field_name} with selector {selector}: {e}")
                continue
        return False
