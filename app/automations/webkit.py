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


def _looks_like_hhmm(value: str) -> bool:
    """"09:00" のような HH:MM 形式か判定"""
    import re
    return bool(re.match(r"^\d{1,2}:\d{2}", str(value or "")))


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

                # 🔴 HTTP 200 でも本文の <status> を必ず確認すること。
                # WebKit API は認証失敗・バリデーションエラーでも 200 を返し、
                # 本文の <status>（0=正常 / 非0=エラー）と <memo> で成否を示す。
                # HTTP ステータスだけで成功判定すると誤って「成功」と報告してしまう。
                if response.status_code != 200:
                    logger.error(
                        f"[WebKit] HTTP error: {response.status_code} - {response.text[:300]}"
                    )
                    return {
                        "status": "error",
                        "platform": "webkit",
                        "message": f"HTTP エラー: {response.status_code}",
                        "details": response.text[:500],
                    }

                result_status, memo, slipno, error_fields = self._parse_response(
                    response.text
                )

                if result_status == "0":
                    logger.info(f"[WebKit] 登録成功: 伝票番号={slipno}")
                    return {
                        "status": "success",
                        "platform": "webkit",
                        "message": memo or "WebKit への登録に成功しました",
                        "baggage_no": slipno,  # 伝票番号（更新・削除に使う）
                        "response_text": response.text[:200],
                    }
                else:
                    # status が 0 以外、または status が読めない = 登録失敗
                    # memo が空でもエラー項目名から理由を組み立てる
                    if memo:
                        reason = memo
                    elif error_fields:
                        reason = f"入力エラー: {', '.join(error_fields)}"
                    else:
                        reason = "WebKit が想定外の応答を返しました"
                    logger.error(
                        f"[WebKit] 登録失敗 (status={result_status}): {reason}"
                    )
                    return {
                        "status": "error",
                        "platform": "webkit",
                        "message": f"WebKit 登録失敗: {reason}",
                        "details": response.text[:500],
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

    def _parse_response(self, response_text: str) -> tuple:
        """WebKit API のレスポンスXMLから (status, memo, slipno, error_fields) を取り出す

        期待するレスポンス形式:
            <webkit><load_data_result>
                <status>0</status>       … 0=正常, 非0=エラー
                <slipno>...</slipno>      … 伝票番号（登録成功時に採番。CRUDに使う）
                <memo>...</memo>          … 結果メッセージ（エラー理由等）
                <エラー項目/>              … エラー時、要素名がエラー対象フィールド名
            </load_data_result></webkit>

        パースできない場合は (None, 生テキスト, "", []) を返す（= 成功扱いにしない）。
        """
        from xml.etree.ElementTree import fromstring, ParseError
        try:
            root = fromstring(response_text)
            result = root.find(".//load_data_result")
            scope = result if result is not None else root
            status_el = scope.find("status")
            memo_el = scope.find("memo")
            slipno_el = scope.find("slipno")
            status = status_el.text.strip() if status_el is not None and status_el.text else None
            memo = memo_el.text.strip() if memo_el is not None and memo_el.text else ""
            slipno = slipno_el.text.strip() if slipno_el is not None and slipno_el.text else ""
            # status/slipno/memo 以外の子要素 = エラー項目（フィールド名）
            error_fields = [
                el.tag for el in scope
                if el.tag not in ("status", "slipno", "memo")
            ]
            return status, memo, slipno, error_fields
        except (ParseError, AttributeError) as e:
            logger.error(f"[WebKit] レスポンス解析失敗: {e} / 本文: {response_text[:200]}")
            return None, response_text[:200], "", []

    async def delete_case(self, slipno: str) -> Dict[str, Any]:
        """登録済み荷物を削除（CRUD の Delete。operation=D。実環境検証済み）

        Args:
            slipno: 登録時に採番された伝票番号（post_case の baggage_no）
        """
        if not self.api_key or not self.person_id:
            return {"status": "error", "platform": "webkit",
                    "message": "WebKit API key or Person ID not configured"}

        webkit = Element('webkit')
        SubElement(webkit, 'apikey').text = self.api_key
        SubElement(webkit, 'personid').text = self.person_id
        ld = SubElement(webkit, 'load_data')
        SubElement(ld, 'operation').text = 'D'
        SubElement(ld, 'slipno').text = slipno
        xml_data = tostring(webkit, encoding='utf-8')

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url, content=xml_data,
                    headers={"Content-Type": "application/xml; charset=UTF-8"},
                )
            if response.status_code != 200:
                return {"status": "error", "platform": "webkit",
                        "message": f"HTTP エラー: {response.status_code}"}
            status, memo, _, error_fields = self._parse_response(response.text)
            if status == "0":
                logger.info(f"[WebKit] 削除成功: 伝票番号={slipno}")
                return {"status": "success", "platform": "webkit",
                        "message": f"WebKit 荷物 {slipno} を削除しました",
                        "baggage_no": slipno}
            reason = memo or (f"エラー項目: {', '.join(error_fields)}"
                              if error_fields else "削除失敗")
            logger.error(f"[WebKit] 削除失敗 (status={status}): {reason}")
            return {"status": "error", "platform": "webkit",
                    "message": f"WebKit 削除失敗: {reason}"}
        except Exception as e:
            logger.error(f"[WebKit] 削除エラー: {e}")
            return {"status": "error", "platform": "webkit",
                    "message": f"{type(e).__name__}: {str(e)}"}

    def _build_load_registration_xml(self, case_data: Dict[str, Any]) -> bytes:
        """荷物登録用XMLを構築（WebKIT API仕様書「2 荷物登録」準拠）

        🔴 【重要】仕様書の正しい構造:
          <webkit>
            <apikey/><personid/>
            <load_data>
              <operation>I</operation>   ← load_data の中！
              <memberid/> ... 各フィールド ...
            </load_data>
          </webkit>

        必須項目(〇): operation, memberid, loaddate, loaddatetype,
          loadprefecture, loadarea, destdate, destdatetype, destprefecture,
          destarea, loadkind, packagetype, weight, carkindtype, mix,
          opentype, charge, charge_taxtype, toll_flg
        - weight は【トン】単位（4.1形式）。kg入力を1000で割る
        - loadarea/destarea は市区町村（例: 港区）。分割入力の pick_city 等を使う
        """
        from app.constants.webkit_codes import (
            get_webkit_car_code, get_cargo_shape_code,
        )
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        webkit = Element('webkit')
        SubElement(webkit, 'apikey').text = self.api_key or ''
        SubElement(webkit, 'personid').text = self.person_id or ''

        load = SubElement(webkit, 'load_data')

        def add(tag, value):
            SubElement(load, tag).text = "" if value is None else str(value)

        # --- 認証・コマンド ---
        add('operation', 'I')                         # I=登録【必須】
        add('memberid', (self.person_id or '')[:12])  # 会員ID=担当者ID前方12桁【必須】

        # --- 積地（日時+都道府県+市区町村） ---
        pickup_date = M.parse_date(case_data.get("pickup_date"))
        pickup_time = case_data.get("pickup_time") or "09:00"
        add('loaddate', f"{pickup_date} {pickup_time}")           # 積日時【必須】
        add('loaddatetype', self._datetime_type(
            case_data.get("loading_time_option")))               # 積日時指定区分【必須】
        add('loadprefecture',
            get_prefecture_code(case_data.get("pick_location", "")) or '17')  # 【必須】
        pick_city = case_data.get("pick_city") or M.extract_city(
            case_data.get("pick_location", "")) or ""
        add('loadarea', pick_city)                               # 積地地区（市区町村）【必須】
        if case_data.get("pick_address"):
            add('loadaddress', case_data["pick_address"])        # 積地住所（任意）

        # --- 卸地 ---
        drop_date = M.parse_date(case_data.get("drop_date")) or M.next_day(pickup_date)
        drop_time = case_data.get("drop_time") or "午前"
        # 「午前」等の非HH:MM表記は WebKIT の日時形式に合わないため 09:00 に丸める
        if not _looks_like_hhmm(drop_time):
            drop_time = "09:00"
        add('destdate', f"{drop_date} {drop_time}")              # 卸日時【必須】
        add('destdatetype', self._datetime_type(
            case_data.get("unloading_time_option")))             # 卸日時指定区分【必須】
        add('destprefecture',
            get_prefecture_code(case_data.get("drop_location", "")) or '30')  # 【必須】
        drop_city = case_data.get("drop_city") or M.extract_city(
            case_data.get("drop_location", "")) or ""
        add('destarea', drop_city)                              # 卸地地区（市区町村）【必須】
        if case_data.get("drop_address"):
            add('destaddress', case_data["drop_address"])

        # --- 荷物 ---
        cargo_type = case_data.get("cargo_type") or "その他"
        loadkind_code = get_cargo_type_code(cargo_type) or '21'
        add('loadkind', loadkind_code)                          # 輸送品区分【必須】
        # loadkind=21(その他) の場合は輸送品区分その他の記述が必須
        if loadkind_code == '21':
            add('loadkind_other', cargo_type[:32])
        # 輸送形状: Trabox 荷姿(パレット/その他) or package_type。既定 その他(10)
        package_name = case_data.get("package_type", "その他")
        packagetype_code = get_cargo_shape_code(package_name)
        add('packagetype', packagetype_code)                    # 輸送形状区分【必須】
        # packagetype=10(その他) の場合は輸送形状その他の記述が必須
        if packagetype_code == '10':
            add('packagetype_other', (package_name if package_name != "その他"
                                      else cargo_type)[:32])
        add('weight', self._weight_to_ton(case_data.get("cargo_weight")))   # 重量(t)【必須】
        add('carkindtype',
            get_webkit_car_code(case_data.get("vehicle_type", "")))  # 希望車種【必須】

        # --- 積合せ（1:可 2:不可 9:未選択）: Trabox share と整合 ---
        share = case_data.get("share", "不可")
        add('mix', '1' if share == "可能" else '2')            # 【必須】

        # --- 公開範囲（1:すべて 5:指定） ---
        add('opentype', '5' if case_data.get("visibility") == "限定" else '1')  # 【必須】

        # --- 運賃 ---
        freight = M.format_freight(case_data.get("freight_rate")) or '0'
        add('charge', freight)                                  # 希望運賃【必須】
        add('charge_taxtype', '1')                              # 1:課税【必須】
        add('charge_nego',
            '1' if case_data.get("freight_negotiable") else '2')  # 応相談(任意)

        # --- 高速代の別途支払（0:なし 1:あり） ---
        add('toll_flg',
            '1' if case_data.get("highway_fee") == "別途支払う" else '0')  # 【必須】

        # --- 担当情報（任意。空欄なら担当者IDの登録情報が使われる） ---
        if case_data.get("contact_name"):
            add('personname', case_data["contact_name"])
        if case_data.get("contact_phone"):
            add('portablephone', case_data["contact_phone"])
        if case_data.get("remarks"):
            add('note1', case_data["remarks"])

        # --- 件数・物流階層 ---
        # reg_number: 登録件数（既定1）
        # logistics_tiers: 実運送体制の階層数（2024年物流法改正対応の必須項目）。
        #   1 = 自社運送（元請が実運送、下請けなし）
        add('reg_number', str(case_data.get("truck_count") or 1))
        add('logistics_tiers', str(case_data.get("logistics_tiers") or 1))

        return tostring(webkit, encoding='utf-8')

    @staticmethod
    def _datetime_type(option: str) -> str:
        """積/卸日時指定区分（1:以降 2:必着 3:迄 9:指定なし）。既定 1:以降"""
        mapping = {"以降": "1", "必着": "2", "迄": "3", "指定なし": "9"}
        return mapping.get(option or "", "1")

    @staticmethod
    def _weight_to_ton(cargo_weight) -> str:
        """荷物重量(kg) → トン（WebKIT weight は 4.1 形式のトン単位）

        例: 1500kg → "1.5"、350kg → "0.4"（小数第1位に丸め）
        """
        try:
            kg = float(cargo_weight)
        except (TypeError, ValueError):
            return "0.0"
        return f"{round(kg / 1000.0, 1)}"

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
