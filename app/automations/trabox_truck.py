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

            # 🔴 場所/車両/運賃/備考の行はラベルが .label-wrapper に無い（重複or単位付き）
            #    ため row_selector では取れない。フォームは固定順なので位置(nth)で特定する。
            #    0:空車地日時 1:空車地場所 2:行先地日時 3:行先地場所
            #    4:他空車地 5:他行先地 6:車両 7:最低運賃 8:担当者 9:備考
            rows = page.locator(".tbx-form-item")

            # --- 1. 空車地 日時（ラベルは有効） ---
            await self._select_datetime(
                page, "空車地", vacant_date,
                list(vacant_time) if vacant_time else None,
            )
            # --- 2. 空車地 都道府県+市区町村（行 index 1） ---
            loc0 = rows.nth(1)
            await self._select_prefecture(page, "都道府県", vacant_pref, row_locator=loc0)
            if vacant_city:
                await self._select_city(page, "都道府県", vacant_city, row_locator=loc0)

            # --- 3. 行先地 日時 ---
            await self._select_datetime(
                page, "行先地", dest_date,
                list(dest_time) if dest_time else None,
            )
            # --- 4. 行先地 都道府県+市区町村（行 index 3） ---
            loc1 = rows.nth(3)
            await self._select_prefecture(page, "都道府県", dest_pref, row_locator=loc1)
            if dest_city:
                await self._select_city(page, "都道府県", dest_city, row_locator=loc1)

            # --- 5/6. その他対応可能 空車地/行先地（任意・複数県。行 index 4/5） ---
            await self._select_able_prefs(page, rows.nth(4),
                                          td.get("vacant_able_prefs") or [])
            await self._select_able_prefs(page, rows.nth(5),
                                          td.get("dest_able_prefs") or [])
            # 複数選択ドロップダウンが開いたままだと次行に被るので閉じる
            await page.mouse.click(3, 3)
            await page.wait_for_timeout(300)

            # --- 7. 車両（重量クラス + 車種）: 行 index 6, 2セレクト ---
            vrow = rows.nth(6)
            await vrow.scroll_into_view_if_needed(timeout=TRABOX_TIMEOUTS["action"])
            await self._select_ant_option(page, vrow.locator(".ant-select").nth(0), weight_class)
            await self._select_ant_option(page, vrow.locator(".ant-select").nth(1), vehicle_option)

            # --- 8. 最低運賃（税別。行 index 7）: 応談ならチェック、それ以外は金額 ---
            prow = rows.nth(7)
            if freight_negotiable or not freight:
                nego = prow.locator(".ant-checkbox-wrapper").first
                if await nego.count():
                    await nego.click(timeout=TRABOX_TIMEOUTS["action"])
                    logger.info("[Trabox空車] 最低運賃: 応談にチェック")
            else:
                await prow.locator("input.ant-input").first.fill(
                    freight, timeout=TRABOX_TIMEOUTS["action"])

            # --- 9. 担当者（必須）: 行 index 8 の AutoComplete に直接入力 ---
            #    🔴 空車フォームは荷物と違い「担当者を変更する」チェックが無く、担当者名が
            #    未入力だと「担当者名を入力してください」で送信できない。必ず入力する。
            contact = str(td.get("contact_name") or "担当").strip()
            crow = rows.nth(8)
            cinput = crow.locator("input[type='search'], input.ant-input, input").first
            await cinput.click(timeout=TRABOX_TIMEOUTS["action"])
            await cinput.fill(contact, timeout=TRABOX_TIMEOUTS["action"])
            await page.wait_for_timeout(300)
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(300)
            if not (await cinput.input_value()):
                # AutoComplete がブラーで消える場合は Enter 確定
                await cinput.click(timeout=TRABOX_TIMEOUTS["action"])
                await cinput.fill(contact, timeout=TRABOX_TIMEOUTS["action"])
                await page.wait_for_timeout(300)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(300)
            logger.info(f"[Trabox空車] 担当者入力: {contact}")

            # --- 10. 備考（任意。行 index 9） ---
            if td.get("remarks"):
                await rows.nth(9).locator("textarea").first.fill(
                    str(td["remarks"]), timeout=TRABOX_TIMEOUTS["action"])

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

    async def _select_able_prefs(self, page, row, prefs) -> None:
        """「その他対応可能◯◯」の複数県 select に県を追加（任意）。row は行ロケータ。"""
        if not prefs or not await row.count():
            return
        for pref in prefs:
            short = M.normalize_prefecture(pref)
            if not short:
                continue
            try:
                await self._select_prefecture(page, "", short, row_locator=row)
            except Exception as e:
                logger.warning(f"[Trabox空車] その他対応可能 {pref} 追加スキップ: {e}")

    async def delete_truck(self, truck_data: Dict[str, Any]) -> Dict[str, Any]:
        """空車掲載を /truck/list から削除する。

        🔴 Trabox 空車投稿は伝票番号を返さないため、掲載を「内容一致」で特定する。
        空車地/行先地の市区町村・県と空車日で一致する行が **ちょうど1件** の時だけ
        削除する（他社/他案件の誤削除を防ぐ安全策）。
        """
        vacant_city = truck_data.get("vacant_city") or ""
        dest_city = truck_data.get("dest_city") or ""
        vacant_pref = M.normalize_prefecture(truck_data.get("vacant_pref", "")) or ""
        dest_pref = M.normalize_prefecture(truck_data.get("dest_pref", "")) or ""
        vdate = M.parse_date(truck_data.get("vacant_date")) or ""
        # 一覧表示の日付断片（例 2026-09-28 → "9/28"）
        md = ""
        if vdate:
            _, mo, dy = vdate.split("-")
            md = f"{int(mo)}/{int(dy)}"
        needles = [n for n in (vacant_city, dest_city, md) if n]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
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
                await page.goto("https://www.trabox.com/truck/list",
                                wait_until="domcontentloaded",
                                timeout=TRABOX_TIMEOUTS["navigation"])
                await page.wait_for_selector("tr.ant-table-row",
                                             timeout=TRABOX_TIMEOUTS["navigation"])
                await page.wait_for_timeout(1500)

                # 🔴 一覧はページネーションあり＋sticky header がクリックを阻む。
                #    一致行は「見つけたページ上」で即削除する必要がある（ページ送りすると
                #    その行が現在DOMから外れ削除クリックが空振りするため）。
                async def _scan_current_page():
                    """現在ページで一致行の data-row-key 一覧を返す"""
                    keys = []
                    rows = page.locator("tr.ant-table-row")
                    for i in range(await rows.count()):
                        txt = (await rows.nth(i).inner_text()).replace("\n", " ")
                        if (all(nd in txt for nd in needles)
                                and vacant_pref in txt and dest_pref in txt):
                            keys.append(await rows.nth(i).get_attribute("data-row-key"))
                    return keys

                async def _next_page():
                    moved = await page.evaluate(
                        "() => {const ns=[...document.querySelectorAll('li.ant-pagination-next')];"
                        "const nx=ns[ns.length-1];"
                        "if(!nx||nx.classList.contains('ant-pagination-disabled'))return false;"
                        "(nx.querySelector('button')||nx).click();return true;}"
                    )
                    if moved:
                        await page.wait_for_timeout(1400)
                    return moved

                # 事前カウント（安全策：一致は1件のみ）
                total = 0
                while True:
                    total += len(await _scan_current_page())
                    if not await _next_page():
                        break
                logger.info(f"[Trabox空車削除] 一致件数={total} needles={needles}")
                if total == 0:
                    return {"status": "success", "platform": "trabox",
                            "message": "該当掲載なし（既に削除済みとみなす）"}
                if total > 1:
                    return {"status": "error", "platform": "trabox",
                            "message": f"一致が{total}件あり安全のため削除中止。手動で削除してください"}

                # 削除パス：一致行を見つけたページ上で削除→確認モーダルで「削除」確定
                await page.goto("https://www.trabox.com/truck/list",
                                wait_until="domcontentloaded",
                                timeout=TRABOX_TIMEOUTS["navigation"])
                await page.wait_for_timeout(2000)
                deleted = False
                while True:
                    keys = await _scan_current_page()
                    if keys:
                        await page.evaluate(
                            """(key) => {
                              const row=document.querySelector(`tr[data-row-key="${key}"]`);
                              if(!row) return false;
                              const del=[...row.querySelectorAll('button')]
                                .find(b=>(b.textContent||'').includes('削除'));
                              if(del){del.click();return true;} return false;
                            }""", keys[0])
                        await page.wait_for_timeout(1200)
                        # 確認モーダルは [キャンセル, 削除]。テキストで「削除」を押す。
                        confirmed = await page.evaluate(
                            """() => {const bs=[...document.querySelectorAll(
                                '.ant-modal button, .ant-modal-confirm button')];
                              const ok=bs.find(b=>/削除|はい|OK|確定|実行/.test(b.textContent||''));
                              if(ok){ok.click();return ok.textContent.trim();} return null;}"""
                        )
                        logger.info(f"[Trabox空車削除] 確認ボタン={confirmed}")
                        await page.wait_for_timeout(2500)
                        deleted = True
                        break
                    if not await _next_page():
                        break
                if not deleted:
                    return {"status": "error", "platform": "trabox",
                            "message": "削除対象行を現在ページで特定できず"}

                # 🔴 削除後に本当に消えたか検証（誤検知防止）。一覧を再走査して残存なら失敗。
                await page.goto("https://www.trabox.com/truck/list",
                                wait_until="domcontentloaded",
                                timeout=TRABOX_TIMEOUTS["navigation"])
                await page.wait_for_timeout(2000)
                for _pg in range(1, 15):
                    rws = page.locator("tr.ant-table-row")
                    for i in range(await rws.count()):
                        txt = (await rws.nth(i).inner_text()).replace("\n", " ")
                        if (all(nd in txt for nd in needles)
                                and vacant_pref in txt and dest_pref in txt):
                            logger.error("[Trabox空車削除] 削除後も掲載が残存")
                            return {"status": "error", "platform": "trabox",
                                    "message": "削除操作後も掲載が残っています（要手動確認）"}
                    moved = await page.evaluate(
                        "() => {const ns=[...document.querySelectorAll('li.ant-pagination-next')];"
                        "const nx=ns[ns.length-1];"
                        "if(!nx||nx.classList.contains('ant-pagination-disabled'))return false;"
                        "(nx.querySelector('button')||nx).click();return true;}"
                    )
                    if not moved:
                        break
                    await page.wait_for_timeout(1300)
                logger.info("[Trabox空車削除] 削除完了（残存なし検証済み）")
                return {"status": "success", "platform": "trabox",
                        "message": "Trabox の空車掲載を削除しました"}
            except Exception as e:
                logger.error(f"[Trabox空車削除] エラー: {e}")
                return {"status": "error", "platform": "trabox",
                        "message": f"{type(e).__name__}: {str(e)[:200]}"}
            finally:
                await context.close()
                await browser.close()

    async def _submit_truck(self, page) -> None:
        """登録ボタン→確認モーダル→成功判定。
        🔴 成功判定は「/truck/register から遷移したか」で厳密に行う（generic テキスト
        一致は誤検知しうる）。遷移しない場合はバリデーションエラーを収集して例外にする。"""
        await self.debug_capture.capture_screenshot("truck_before_submit")
        await page.click(M.SUBMIT_BUTTON_SELECTOR, timeout=TRABOX_TIMEOUTS["action"])
        # 確認モーダルがあれば確定
        try:
            confirm = page.locator(
                ".ant-modal:visible button.ant-btn-primary, "
                ".ant-modal:visible button.ant-btn-dangerous"
            ).first
            await confirm.click(timeout=5000)
            logger.info("[Trabox空車] 確認モーダルで確定")
        except Exception:
            pass
        # 遷移待ち（/truck/register から離れれば成功）
        try:
            await page.wait_for_url(
                lambda url: "/truck/register" not in url,
                timeout=TRABOX_TIMEOUTS["navigation"],
            )
        except Exception:
            pass
        await page.wait_for_timeout(1000)

        if "/truck/register" not in page.url:
            logger.info(f"[Trabox空車] 送信成功（遷移先={page.url}）")
            return

        # まだ登録ページ = 送信不成立。バリデーションエラーを収集して報告
        errs = []
        try:
            rows = page.locator(".tbx-form-item.has-validation-error, "
                                ".tbx-form-item:has(.ant-form-item-explain-error)")
            for i in range(min(await rows.count(), 6)):
                t = (await rows.nth(i).inner_text()).replace("\n", " ").strip()
                if t:
                    errs.append(t[:60])
        except Exception:
            pass
        await self.debug_capture.capture_screenshot("truck_submit_failed")
        detail = " / ".join(errs) if errs else "原因不明（遷移せず）"
        raise Exception(f"Trabox 空車の送信に失敗：{detail}")
