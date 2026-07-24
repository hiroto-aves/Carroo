"""WebKIT 空車（車両情報）API 投稿

荷物の LoadInfo と並行構造の CarInfo エンドポイントを扱う。
- エンドポイント: https://www.wkit.jp/api/CarInfo
- メソッド: POST / Content-Type: application/xml; charset=UTF-8
- 認証: apikey（20桁・会員共通）+ personid（14桁・担当者ごと）
- operation: I=登録 / U=更新 / D=削除
- レスポンスの result 要素は <car_data_result>（荷物は load_data_result）

truck_data（呼び出し側が渡す dict）の想定キー:
    vacant_date "YYYY-MM-DD", vacant_time "HH:MM", vacant_pref, vacant_city
    dest_date, dest_time, dest_pref, dest_city
    vacant_able_prefs: [県名...]  （その他対応可能空車地→load_able1..10）
    dest_able_prefs:   [県名...]  （その他対応可能行先地→dest_able1..10）
    vehicle_type, load_weight(積載量t), max_weight(最大積載量t)
    carplate, driver, min_freight, share("可能"/"不可"), visibility("限定"/その他)
    contact_name, contact_phone, remarks
"""
import logging
from typing import Dict, Any
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring, ParseError

import httpx

from app.config import settings
from app.constants.webkit_codes import get_prefecture_code, get_webkit_car_code

logger = logging.getLogger(__name__)


def _looks_like_hhmm(value: str) -> bool:
    import re
    return bool(re.match(r"^\d{1,2}:\d{2}", str(value or "")))


def _fmt_datetime(date_str: str, time_str: str) -> str:
    """"2026-09-22", "09:00" → "2026-09-22 09:00:00"（秒まで。CarInfo 仕様）"""
    t = time_str if _looks_like_hhmm(time_str) else "09:00"
    if len(t) == 5:  # HH:MM → HH:MM:00
        t = f"{t}:00"
    return f"{date_str} {t}"


class WebkitTruckAutomation:
    """WebKIT 空車（CarInfo）API クライアント（登録/更新/削除）"""

    def __init__(self, person_id: str = None):
        self.api_url = "https://www.wkit.jp/api/CarInfo"
        self.api_key = settings.WEBKIT_API_KEY           # 会員共通
        self.person_id = person_id or getattr(settings, "WEBKIT_PERSON_ID", None)
        self.timeout = 30.0

    # ---------------- 公開メソッド（荷物 WebkitAutomation と同じ形） ----------------

    async def post_truck(self, truck_data: Dict[str, Any]) -> Dict[str, Any]:
        """空車を登録（operation=I）。成功時 baggage_no に伝票番号を返す。"""
        return await self._send(self._build_xml(truck_data, "I"), action="登録")

    async def update_truck(self, slipno: str, truck_data: Dict[str, Any]) -> Dict[str, Any]:
        """登録済み空車を更新（operation=U・全項目上書き）。slipno 必須。"""
        return await self._send(
            self._build_xml(truck_data, "U", slipno=slipno), action="更新", slipno=slipno
        )

    async def delete_truck(self, slipno: str) -> Dict[str, Any]:
        """登録済み空車を削除（operation=D）。"""
        webkit = Element("webkit")
        SubElement(webkit, "apikey").text = self.api_key or ""
        SubElement(webkit, "personid").text = self.person_id or ""
        car = SubElement(webkit, "car_data")
        SubElement(car, "operation").text = "D"
        SubElement(car, "slipno").text = slipno
        return await self._send(tostring(webkit, encoding="utf-8"), action="削除", slipno=slipno)

    # ---------------- 内部 ----------------

    async def _send(self, xml_data: bytes, action: str, slipno: str = "") -> Dict[str, Any]:
        if not self.api_key or not self.person_id:
            return {"status": "error", "platform": "webkit",
                    "message": "WebKit API key or Person ID not configured"}
        try:
            logger.debug(f"[WebKit空車] XML:\n{xml_data.decode('utf-8')}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url, content=xml_data,
                    headers={"Content-Type": "application/xml; charset=UTF-8"},
                )
            if response.status_code != 200:
                logger.error(f"[WebKit空車] HTTP {response.status_code}: {response.text[:300]}")
                return {"status": "error", "platform": "webkit",
                        "message": f"HTTP エラー: {response.status_code}"}
            # 🔴 HTTP 200 でも本文の <status>（0=正常）を必ず確認する
            status, memo, ret_slip, error_fields = self._parse_response(response.text)
            if status == "0":
                logger.info(f"[WebKit空車] {action}成功: 伝票番号={ret_slip or slipno}")
                return {"status": "success", "platform": "webkit",
                        "message": memo or f"WebKit 空車を{action}しました",
                        "baggage_no": ret_slip or slipno}
            reason = memo or (f"入力エラー: {', '.join(error_fields)}"
                              if error_fields else f"{action}失敗")
            logger.error(f"[WebKit空車] {action}失敗 (status={status}): {reason}")
            return {"status": "error", "platform": "webkit",
                    "message": f"WebKit 空車{action}失敗: {reason}",
                    "details": response.text[:500]}
        except httpx.TimeoutException as e:
            logger.error(f"[WebKit空車] Timeout: {e}")
            return {"status": "error", "platform": "webkit", "message": f"Request timeout: {e}"}
        except Exception as e:
            logger.error(f"[WebKit空車] Exception: {type(e).__name__}: {e}")
            return {"status": "error", "platform": "webkit",
                    "message": f"{type(e).__name__}: {str(e)}"}

    def _parse_response(self, response_text: str) -> tuple:
        """CarInfo レスポンスから (status, memo, slipno, error_fields) を取り出す。
        result 要素は <car_data_result>。無ければルート直下も探す。"""
        try:
            root = fromstring(response_text)
            result = root.find(".//car_data_result")
            scope = result if result is not None else root
            def txt(tag):
                el = scope.find(tag)
                return el.text.strip() if el is not None and el.text else ""
            status = txt("status") or None
            memo = txt("memo")
            slipno = txt("slipno")
            error_fields = [el.tag for el in scope
                            if el.tag not in ("status", "slipno", "memo")]
            return status, memo, slipno, error_fields
        except (ParseError, AttributeError) as e:
            logger.error(f"[WebKit空車] レスポンス解析失敗: {e} / 本文: {response_text[:200]}")
            return None, response_text[:200], "", []

    def _build_xml(self, td: Dict[str, Any], operation: str, slipno: str = None) -> bytes:
        """CarInfo 登録/更新XML（WebKIT API仕様書「6 車両登録」「7 車両更新」準拠）

        構造: <webkit><apikey/><personid/><car_data>
                <operation/>[<slipno/>] ...各フィールド... </car_data></webkit>
        必須(〇): operation, vacantdate, vacantprefecture, destdate,
                  destprefecture, carkindtype, mix, opentype
        """
        webkit = Element("webkit")
        SubElement(webkit, "apikey").text = self.api_key or ""
        SubElement(webkit, "personid").text = self.person_id or ""
        car = SubElement(webkit, "car_data")

        def add(tag, value):
            SubElement(car, tag).text = "" if value is None else str(value)

        add("operation", operation)                       # I/U【必須】
        add("memberid", (self.person_id or "")[:12])      # 会員ID=担当者ID前方12桁
        if operation == "U":
            add("slipno", slipno)                         # 更新対象伝票番号【必須】

        # --- 空車地（日時+県+地区） ---
        add("vacantdate", _fmt_datetime(td.get("vacant_date"),
                                        td.get("vacant_time") or "09:00"))  # 【必須】
        add("vacantprefecture",
            get_prefecture_code(td.get("vacant_pref", "")) or "17")         # 【必須】既定=東京(17)
        add("vacantarea", td.get("vacant_city") or "")

        # --- 行先地 ---
        add("destdate", _fmt_datetime(td.get("dest_date"),
                                      td.get("dest_time") or "09:00"))      # 【必須】
        add("destprefecture",
            get_prefecture_code(td.get("dest_pref", "")) or "30")           # 【必須】既定=大阪(30)
        add("destarea", td.get("dest_city") or "")

        # --- 車種・積載量 ---
        add("carkindtype", get_webkit_car_code(td.get("vehicle_type", "")))  # 【必須】
        if td.get("load_weight") not in (None, ""):
            add("weight", td["load_weight"])              # 積載量(t)
        if td.get("max_weight") not in (None, ""):
            add("maxweight", td["max_weight"])            # 最大積載量(t)
        if td.get("carplate"):
            add("carplate", td["carplate"])               # 車番
        if td.get("driver"):
            add("driver", td["driver"])                   # 乗務員氏名

        # --- 積合せ（1:可 2:不可）【必須】 ---
        add("mix", "1" if td.get("share") == "可能" else "2")

        # --- 情報公開（1:すべて 5:指定）【必須】 ---
        add("opentype", "5" if td.get("visibility") == "限定" else "1")

        # --- その他対応可能：積地可能県 load_able1..10 / 卸地可能県 dest_able1..10 ---
        for i, pref in enumerate((td.get("vacant_able_prefs") or [])[:10], start=1):
            code = get_prefecture_code(pref)
            if code:
                add(f"load_able{i}", code)
        for i, pref in enumerate((td.get("dest_able_prefs") or [])[:10], start=1):
            code = get_prefecture_code(pref)
            if code:
                add(f"dest_able{i}", code)

        # --- 担当情報（任意。空欄なら担当者IDの登録情報が使われる） ---
        if td.get("contact_name"):
            add("personname", td["contact_name"])
        if td.get("contact_phone"):
            add("portablephone", td["contact_phone"])
        if td.get("remarks"):
            add("note1", td["remarks"])

        return tostring(webkit, encoding="utf-8")
