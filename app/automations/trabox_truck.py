"""Trabox 空車（トラック空き）投稿（Playwright）

荷物の TraboxAutomation を継承し、ログイン・ナビ・日時/都道府県/市区町村ピッカー・
送信判定などの既存ヘルパーを流用する。登録ページは /truck/register。

truck_data の想定キー（webkit_truck.py と共通）:
    vacant_date "YYYY-MM-DD", vacant_time "HH:MM", vacant_pref, vacant_city
    dest_date, dest_time, dest_pref, dest_city
    vacant_able_prefs:[県名...], dest_able_prefs:[県名...]
    vehicle_type, truck_weight（積載トンクラス 例"2t"）
    min_freight, freight_negotiable, contact_name, remarks
"""
import logging
from typing import Dict, Any

from playwright.async_api import async_playwright

from app.automations.trabox import TraboxAutomation
from app.automations.trabox_form_mapper import TraboxFormMapper as M
from app.constants.trabox_config import TRABOX_TIMEOUTS
from app.utils.debug_capture import DebugCapture
from app.utils.error_handler import ErrorHandler
from app.utils.structured_logging import structured_logger

logger = logging.getLogger(__name__)

TRABOX_TRUCK_REGISTER_URL = "https://www.trabox.com/truck/register"


class TraboxTruckAutomation(TraboxAutomation):
    """Trabox 空車の登録（＋将来の更新/削除）。TraboxAutomation の資産を流用。"""

    async def post_truck(self, truck_data: Dict[str, Any]) -> Dict[str, Any]:
        """空車を /truck/register に登録する。"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            # 🔴 TZ=Asia/Tokyo 必須（UTC だと日時ピッカーが確定しない）。縦長ビューポート。
            context = await browser.new_context(
                viewport={"width": 1440, "height": 2600},
                timezone_id="Asia/Tokyo", locale="ja-JP",
            )
            page = await context.new_page()
            self.debug_capture = DebugCapture(page)
            try:
                await self._step_navigate_to_dashboard(page)
                if await self._is_login_page(page):
                    await self._step_login(page)
                    await self._step_navigate_to_dashboard(page)

                await page.goto(
                    TRABOX_TRUCK_REGISTER_URL,
                    wait_until="domcontentloaded",
                    timeout=TRABOX_TIMEOUTS["navigation"],
                )
                await page.wait_for_selector(
                    ".tbx-form-item", timeout=TRABOX_TIMEOUTS["navigation"]
                )
                await self._fill_truck_form(page, truck_data)
                await self._submit_truck(page)

                logger.info("[Trabox空車] 登録成功")
                return {"status": "success", "platform": "trabox",
                        "message": "Trabox に空車を登録しました"}
            except Exception as e:
                error = ErrorHandler.handle_posting_error(
                    e, self.user_id, self.case_id, "trabox", step="truck_post",
                    screenshots=self._get_screenshot_paths(),
                    dom_snapshot=await self.debug_capture.capture_dom_snapshot()
                    if self.debug_capture else None,
                )
                await self._handle_posting_error(page, error)
                raise
            finally:
                await context.close()
                await browser.close()

    async def _fill_truck_form(self, page, td: Dict[str, Any]) -> None:
        """/truck/register のフォームを入力（既存ヘルパー流用）。"""
        try:
            vacant_date = M.parse_date(td.get("vacant_date"))
            vacant_time = M.parse_time(td.get("vacant_time"))
            dest_date = M.parse_date(td.get("dest_date"))
            dest_time = M.parse_time(td.get("dest_time"))
            vacant_pref = M.normalize_prefecture(td.get("vacant_pref", ""))
            dest_pref = M.normalize_prefecture(td.get("dest_pref", ""))
            vacant_city = td.get("vacant_city") or ""
            dest_city = td.get("dest_city") or ""
            weight_class = (td.get("truck_weight")
                            if td.get("truck_weight") in M.TRUCK_WEIGHT_OPTIONS
                            else M.weight_to_class(td.get("load_weight_kg")))
            vehicle_option = M.vehicle_to_option(td.get("vehicle_type", ""))
            freight = M.format_freight(td.get("min_freight"))
            freight_negotiable = td.get("freight_negotiable") in (True, "true", "yes", "1", 1)

            if not vacant_date or not dest_date:
                raise ValueError("空車日・行先日が不正です")
            if not vacant_pref or not dest_pref:
                raise ValueError("空車県・行先県が不正です")

            # --- 1. 空車地 日時 ---
            await self._select_datetime(
                page, "空車地", vacant_date,
                list(vacant_time) if vacant_time else None,
            )
            # --- 2. 空車地 都道府県+市区町村（1つ目の「都道府県」行） ---
            loc0 = page.locator(M.row_selector("都道府県")).nth(0)
            await self._select_prefecture(page, "都道府県", vacant_pref, row_locator=loc0)
            if vacant_city:
                await self._select_city(page, "都道府県", vacant_city, row_locator=loc0)

            # --- 3. 行先地 日時 ---
            await self._select_datetime(
                page, "行先地", dest_date,
                list(dest_time) if dest_time else None,
            )
            # --- 4. 行先地 都道府県+市区町村（2つ目の「都道府県」行） ---
            loc1 = page.locator(M.row_selector("都道府県")).nth(1)
            await self._select_prefecture(page, "都道府県", dest_pref, row_locator=loc1)
            if dest_city:
                await self._select_city(page, "都道府県", dest_city, row_locator=loc1)

            # --- 5/6. その他対応可能 空車地/行先地（任意・複数県） ---
            await self._select_able_prefs(page, "その他対応可能空車地",
                                          td.get("vacant_able_prefs") or [])
            await self._select_able_prefs(page, "その他対応可能行先地",
                                          td.get("dest_able_prefs") or [])

            # --- 7. 車両（重量クラス + 車種）: 荷物と同じ2セレクト ---
            vrow = page.locator(M.row_selector("車両重量")).first
            await self._select_ant_option(page, vrow.locator(".ant-select").nth(0), weight_class)
            await self._select_ant_option(page, vrow.locator(".ant-select").nth(1), vehicle_option)

            # --- 8. 最低運賃（税別）: 応談ならチェック、それ以外は金額 ---
            if freight_negotiable or not freight:
                nego = page.locator(
                    f"{M.row_selector('最低運賃')} .ant-checkbox-wrapper"
                ).first
                if await nego.count():
                    await nego.click(timeout=TRABOX_TIMEOUTS["action"])
                    logger.info("[Trabox空車] 最低運賃: 応談にチェック")
            else:
                await page.locator(
                    f"{M.row_selector('最低運賃')} input.ant-input"
                ).first.fill(freight, timeout=TRABOX_TIMEOUTS["action"])

            # --- 9. 担当者（任意） ---
            if td.get("contact_name"):
                try:
                    await self._set_contact_person(page, str(td["contact_name"]))
                except Exception as ce:
                    logger.warning(f"[Trabox空車] 担当者設定スキップ: {ce}")

            # --- 10. 備考（任意） ---
            if td.get("remarks"):
                await page.locator(
                    f"{M.row_selector('備考')} textarea"
                ).first.fill(str(td["remarks"]), timeout=TRABOX_TIMEOUTS["action"])

            structured_logger.log_event(
                "trabox_truck_fill", self.user_id, self.case_id, "trabox",
                details={"vacant": f"{vacant_pref}{vacant_city}",
                         "dest": f"{dest_pref}{dest_city}",
                         "vacant_date": vacant_date, "dest_date": dest_date,
                         "vehicle": vehicle_option, "freight": freight},
            )
        except Exception as e:
            raise ErrorHandler.handle_posting_error(
                e, self.user_id, self.case_id, "trabox", step="truck_fill_form",
                screenshots=self._get_screenshot_paths(),
            )

    async def _select_able_prefs(self, page, row_label: str, prefs) -> None:
        """「その他対応可能◯◯」の複数県 select に県を追加（任意）。"""
        if not prefs:
            return
        row = page.locator(M.row_selector(row_label)).first
        if not await row.count():
            return
        for pref in prefs:
            short = M.normalize_prefecture(pref)
            if not short:
                continue
            try:
                await self._select_prefecture(page, row_label, short, row_locator=row)
            except Exception as e:
                logger.warning(f"[Trabox空車] {row_label} {pref} 追加スキップ: {e}")

    async def _submit_truck(self, page) -> None:
        """登録ボタン→確認モーダル→成功判定（荷物の送信ロジックを踏襲）。"""
        await self.debug_capture.capture_screenshot("truck_before_submit")
        await page.click(M.SUBMIT_BUTTON_SELECTOR, timeout=TRABOX_TIMEOUTS["action"])
        try:
            confirm = page.locator(".ant-modal:visible button.ant-btn-primary").first
            await confirm.click(timeout=5000)
            logger.info("[Trabox空車] 確認モーダルで確定")
        except Exception:
            pass
        try:
            await page.wait_for_load_state("domcontentloaded",
                                           timeout=TRABOX_TIMEOUTS["navigation"])
        except Exception:
            await page.wait_for_timeout(2000)
        if not await self._check_submission_success(page):
            await self.debug_capture.capture_screenshot("truck_submit_uncertain")
            raise Exception("Trabox 空車の送信に失敗（成功メッセージ/遷移なし）")
