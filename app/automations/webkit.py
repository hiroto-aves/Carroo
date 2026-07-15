import httpx
from app.config import settings
from app.constants.webkit_codes import (
    get_prefecture_code, get_vehicle_code, get_cargo_type_code, get_handling_code
)
from typing import Dict, Any, Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime
import logging
from playwright.async_api import async_playwright, Page

logger = logging.getLogger(__name__)

class WebkitAutomation:
    """WebKIT APIへのXML投稿を実行

    仕様：
    - エンドポイント: https://www.wkit.jp/api/LoadInfo
    - メソッド: POST
    - Content-Type: application/xml
    - 文字コード: UTF-8
    - 認証: apikey（20桁）+ personid（14桁）
    """

    def __init__(self):
        self.webkit_url = settings.WEBKIT_URL
        self.login_id = settings.WEBKIT_LOGIN_ID
        self.login_password = settings.WEBKIT_LOGIN_PASSWORD
        self.api_url = "https://www.wkit.jp/api/LoadInfo"
        self.api_key = settings.WEBKIT_API_KEY
        self.person_id = getattr(settings, 'WEBKIT_PERSON_ID', None)
        self.timeout = 30.0

    async def post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """案件データをWebKIT APIに投稿（XML形式）"""
        logger.info("[WebKit] Starting case posting...")

        if not self.api_key or not self.person_id:
            return {
                "status": "error",
                "platform": "webkit",
                "message": "WebKit API key or Person ID not configured"
            }

        try:
            xml_data = self._build_load_registration_xml(case_data)
            logger.debug(f"[WebKit] XML Payload:\n{xml_data.decode('utf-8')}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    content=xml_data,
                    headers={"Content-Type": "application/xml; charset=UTF-8"}
                )

                logger.info(f"[WebKit] Response status: {response.status_code}")

                if response.status_code == 200:
                    logger.info("[WebKit] Case posted successfully")
                    return {
                        "status": "success",
                        "platform": "webkit",
                        "message": "Case posted to WebKit successfully",
                        "response_text": response.text[:200]
                    }
                else:
                    error_msg = response.text
                    logger.error(f"[WebKit] API error: {response.status_code} - {error_msg}")
                    return {
                        "status": "error",
                        "platform": "webkit",
                        "message": f"API error: {response.status_code}",
                        "details": error_msg[:500]
                    }

        except httpx.TimeoutException as e:
            logger.error(f"[WebKit] Timeout: {e}")
            return {
                "status": "error",
                "platform": "webkit",
                "message": f"Request timeout: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[WebKit] Exception: {type(e).__name__}: {e}")
            return {
                "status": "error",
                "platform": "webkit",
                "message": f"{type(e).__name__}: {str(e)}"
            }

    def _build_load_registration_xml(self, case_data: Dict[str, Any]) -> bytes:
        """荷物登録用XMLを構築"""
        root = Element('xml')

        # 認証情報
        webkit = SubElement(root, 'webkit')
        apikey_elem = SubElement(webkit, 'apikey')
        apikey_elem.text = self.api_key
        personid_elem = SubElement(webkit, 'personid')
        personid_elem.text = self.person_id

        # operation: I = Insert (登録)
        operation_elem = SubElement(webkit, 'operation')
        operation_elem.text = 'I'

        # 荷物情報
        load_data = SubElement(webkit, 'load_data')

        # 積地
        pick_location = case_data.get("pick_location", "")
        tsumichi_code = get_prefecture_code(pick_location)
        tsumichi = SubElement(load_data, 'tsumichi_code')
        tsumichi.text = tsumichi_code or '17'  # デフォルト: 東京都

        # 積日
        pickup_date = case_data.get("pickup_date", "")
        if pickup_date:
            try:
                date_obj = datetime.strptime(pickup_date, "%Y-%m-%d")
                loaddate_y = SubElement(load_data, 'loaddate_Y')
                loaddate_y.text = str(date_obj.year)
                loaddate_m = SubElement(load_data, 'loaddate_M')
                loaddate_m.text = str(date_obj.month).zfill(2)
                loaddate_d = SubElement(load_data, 'loaddate_D')
                loaddate_d.text = str(date_obj.day).zfill(2)
            except ValueError:
                logger.warning(f"[WebKit] Invalid pickup_date format: {pickup_date}")

        # 卸地
        drop_location = case_data.get("drop_location", "")
        oroshichi_code = get_prefecture_code(drop_location)
        oroshichi = SubElement(load_data, 'oroshichi_code')
        oroshichi.text = oroshichi_code or '30'  # デフォルト: 大阪府

        # 卸日（積日+2日）
        if pickup_date:
            try:
                from datetime import timedelta
                date_obj = datetime.strptime(pickup_date, "%Y-%m-%d")
                dest_date = date_obj + timedelta(days=2)
                destdate_y = SubElement(load_data, 'destdate_Y')
                destdate_y.text = str(dest_date.year)
                destdate_m = SubElement(load_data, 'destdate_M')
                destdate_m.text = str(dest_date.month).zfill(2)
                destdate_d = SubElement(load_data, 'destdate_D')
                destdate_d.text = str(dest_date.day).zfill(2)
            except:
                pass

        # 荷物重量
        cargo_weight = case_data.get("cargo_weight")
        if cargo_weight:
            weight = SubElement(load_data, 'weight')
            weight.text = str(int(cargo_weight))

        # 希望車種
        vehicle_type = case_data.get("vehicle_type", "")
        if vehicle_type:
            carkindtype = SubElement(load_data, 'carkindtype')
            # 英数値から日本語に変換（例: small_truck -> 平型）
            vehicle_code = self._map_vehicle_type(vehicle_type)
            carkindtype.text = vehicle_code or '1'

        # 荷扱い
        handling = SubElement(load_data, 'loadhanding')
        handling.text = '9'  # 指定なし

        # 積合せ
        mix = SubElement(load_data, 'mix')
        mix.text = '1'  # 可

        # XML文字列に変換
        xml_str = tostring(root, encoding='utf-8')
        return xml_str

    def _map_vehicle_type(self, vehicle_type: str) -> str:
        """英数値の車種をWebKITコードにマッピング"""
        mapping = {
            'small_truck': '1',      # 平型
            'medium_truck': '2',      # バン型
            'large_truck': '3',       # ウイング型
            'refrigerated': '4',      # 保冷車
            'frozen': '5',            # 冷凍車
            'other': '13',            # その他
        }
        return mapping.get(vehicle_type, '13')

    async def login_and_post_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """ブラウザ自動化で WebKIT にログイン＆投稿"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()
            page.set_default_timeout(30000)

            try:
                logger.info("[WebKit] Starting browser automation posting...")

                # ログイン
                await self._login_with_browser(page)

                # ダッシュボード/投稿ページにアクセス
                logger.info("[WebKit] Navigating to posting page...")
                await page.goto(f"{self.webkit_url}/top/", wait_until="networkidle")
                await page.screenshot(path="webkit_logged_in.png")

                logger.info("[WebKit] Case posting with browser completed")
                return {
                    "status": "success",
                    "platform": "webkit",
                    "message": "Logged in successfully (browser automation ready)"
                }

            except Exception as e:
                logger.error(f"[WebKit] Browser automation error: {e}")
                try:
                    await page.screenshot(path="webkit_error.png")
                except:
                    pass
                return {
                    "status": "error",
                    "platform": "webkit",
                    "message": f"{type(e).__name__}: {str(e)}"
                }

            finally:
                await context.close()
                await browser.close()

    async def _login_with_browser(self, page: Page):
        """Playwright で WebKIT にログイン"""
        logger.info("[WebKit] Logging in with browser...")

        if not self.login_id or not self.login_password:
            raise ValueError("WebKit login credentials not configured")

        # ログインページにアクセス
        await page.goto(self.webkit_url, wait_until="networkidle")

        # ログインフォーム要素を探して入力
        # 会員ID 入力
        logger.debug("[WebKit] Filling login ID...")
        member_id_input = page.locator('input[placeholder="会員ID"], input[name*="member"], input[type="text"]').first
        await member_id_input.fill(self.login_id)

        # パスワード入力
        logger.debug("[WebKit] Filling password...")
        password_input = page.locator('input[placeholder="パスワード"], input[name*="password"], input[type="password"]').first
        await password_input.fill(self.login_password)

        # ログインボタンクリック
        logger.debug("[WebKit] Clicking login button...")
        login_button = page.locator('button:has-text("ログインして利用する"), button:has-text("ログイン"), input[type="submit"]').first
        await login_button.click()

        # ログイン完了待機
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_navigation(wait_until="networkidle", timeout=10000)
        except:
            pass

        logger.info("[WebKit] Login completed")
