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

                # ステップ 6: 登録された荷物番号を取得（将来の更新・削除に使用）
                baggage_no = await self._get_registered_baggage_no(page)

                # 成功ログ
                structured_logger.log_posting_completed(
                    self.user_id,
                    self.case_id,
                    "trabox",
                    {
                        "status": "success",
                        "message": "Trabox への投稿に成功しました",
                        "baggage_no": baggage_no,
                    },
                )

                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": "投稿に成功しました",
                    "baggage_no": baggage_no,
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

    async def update_case(
        self, baggage_no: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """登録済み荷物を部分更新（CRUD の Update。実環境調査済み 2026-07-22）

        編集フォームは直接URL（?baggageId=荷物番号&edit=true）で開ける。
        登録フォームと同じ .tbx-form-item 行構造だが、行ラベルが一部異なる:
        「発」→「発日時/発地」、「着」→「着日時/着地」。送信ボタンは「変更」。
        全項目プリフィル済みのため、updates に含まれるフィールドのみ書き換える。

        Args:
            baggage_no: Trabox の荷物番号
            updates: 更新するフィールドのみを含む dict（case_data と同じキー体系）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1440, "height": 1400})
            page = await context.new_page()
            self.debug_capture = DebugCapture(page)

            try:
                await self._step_navigate_to_dashboard(page)
                if await self._is_login_page(page):
                    await self._step_login(page)
                    await self._step_navigate_to_dashboard(page)

                # 編集フォームを直接URLで開く
                edit_url = f"{TRABOX_DASHBOARD_URL}?baggageId={baggage_no}&edit=true"
                await page.goto(
                    edit_url,
                    wait_until="networkidle",
                    timeout=TRABOX_TIMEOUTS["navigation"],
                )
                # 編集ドロワー（荷物情報変更）の描画を待機
                # 🔴 詳細パネルと編集パネルの2枚のドロワーが開き、どちらも
                # 「荷物情報変更」テキストを含むため、フォーム行（.tbx-form-item）を
                # 持つ方 = 編集ドロワーで特定する
                modal = page.locator(
                    ".ant-drawer.ant-drawer-open:has(.tbx-form-item)"
                ).first
                await modal.wait_for(
                    state="visible", timeout=TRABOX_TIMEOUTS["navigation"]
                )
                await page.wait_for_timeout(1000)
                # お知らせモーダル等がクリックを遮ることがあるため先に閉じる
                await self._dismiss_overlays(page)
                await self.debug_capture.capture_screenshot("update_before")

                # --- 発日時（日付・時刻） ---
                if "pickup_date" in updates or "pickup_time" in updates:
                    pickup_date = M.parse_date(updates.get("pickup_date"))
                    pickup_time = M.parse_time(updates.get("pickup_time"))
                    if pickup_date or pickup_time:
                        # 日付未指定で時刻のみ変更の場合もカレンダー操作が必要なため
                        # 日付は必須（未指定なら呼び出し側で現値を渡すこと）
                        if not pickup_date:
                            raise ValueError(
                                "pickup_time のみの更新には pickup_date も指定してください"
                            )
                        await self._select_datetime(
                            page, "発日時/発地", pickup_date,
                            list(pickup_time) if pickup_time else None,
                            root=modal,
                        )
                if "pickup_time" in updates and updates.get("pickup_time"):
                    await modal.locator(M.PICKUP_TIME_TEXT_SELECTOR).fill(
                        str(updates["pickup_time"]),
                        timeout=TRABOX_TIMEOUTS["action"],
                    )

                # --- 着日時 ---
                if "drop_date" in updates or "drop_time" in updates:
                    drop_date = M.parse_date(updates.get("drop_date"))
                    drop_time_parsed = M.parse_time(updates.get("drop_time"))
                    if drop_date:
                        labels = (
                            list(drop_time_parsed) if drop_time_parsed
                            else [M.TRABOX_DEFAULTS["drop_time_label"]]
                        )
                        await self._select_datetime(
                            page, "着日時/着地", drop_date, labels, root=modal
                        )

                # --- 発地・着地 ---
                if "pick_location" in updates:
                    pref = M.normalize_prefecture(updates["pick_location"])
                    city = updates.get("pick_city") or M.extract_city(updates["pick_location"])
                    if pref:
                        await self._select_prefecture(page, "発地", pref, root=modal)
                    if city:
                        await self._select_city(page, "発地", city, root=modal)
                if "drop_location" in updates:
                    pref = M.normalize_prefecture(updates["drop_location"])
                    city = updates.get("drop_city") or M.extract_city(updates["drop_location"])
                    if pref:
                        await self._select_prefecture(page, "着地", pref, root=modal)
                    if city:
                        await self._select_city(page, "着地", city, root=modal)

                # --- 荷種 ---
                if "cargo_type" in updates:
                    cargo_input = modal.locator(
                        f"{M.row_selector('荷種')} input"
                    ).first
                    await cargo_input.fill(
                        str(updates["cargo_type"]), timeout=TRABOX_TIMEOUTS["action"]
                    )
                    await page.keyboard.press("Tab")

                # --- 総重量・希望車両（重量クラス連動） ---
                if "cargo_weight" in updates:
                    weight_input = modal.locator(
                        f"{M.row_selector('総重量')} input.ant-input"
                    ).first
                    await weight_input.fill(
                        str(int(float(updates["cargo_weight"]))),
                        timeout=TRABOX_TIMEOUTS["action"],
                    )
                    row = modal.locator(M.row_selector("希望車両")).first
                    await self._select_ant_option(
                        page, row.locator(".ant-select").nth(0),
                        M.weight_to_class(updates["cargo_weight"]),
                    )

                # --- 車種 ---
                if "vehicle_type" in updates:
                    row = modal.locator(M.row_selector("希望車両")).first
                    await self._select_ant_option(
                        page, row.locator(".ant-select").nth(1),
                        M.vehicle_to_option(updates["vehicle_type"]),
                    )

                # --- 運賃 ---
                if "freight_rate" in updates:
                    freight = M.format_freight(updates["freight_rate"])
                    if freight:
                        freight_input = modal.locator(
                            f"{M.row_selector('運賃')} input.ant-input"
                        ).first
                        await freight_input.fill(
                            freight, timeout=TRABOX_TIMEOUTS["action"]
                        )

                # --- 備考 ---
                if "remarks" in updates:
                    remarks_input = modal.locator(
                        f"{M.row_selector('備考')} textarea"
                    ).first
                    await remarks_input.fill(
                        str(updates["remarks"]), timeout=TRABOX_TIMEOUTS["action"]
                    )

                await self.debug_capture.capture_screenshot("update_filled")

                # 「変更」ボタンで確定
                await modal.locator(
                    "button.ant-btn-primary:has-text('変更')"
                ).first.click(timeout=TRABOX_TIMEOUTS["action"])
                await page.wait_for_timeout(2500)
                await self.debug_capture.capture_screenshot("update_after")

                logger.info(f"[Trabox] 荷物更新成功: {baggage_no} {list(updates.keys())}")
                structured_logger.log_event(
                    "trabox_update",
                    self.user_id,
                    self.case_id,
                    "trabox",
                    details={"baggage_no": baggage_no, "fields": list(updates.keys())},
                )
                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": f"荷物 {baggage_no} を更新しました",
                    "baggage_no": baggage_no,
                    "updated_fields": list(updates.keys()),
                }

            except Exception as e:
                raise ErrorHandler.handle_posting_error(
                    e,
                    self.user_id,
                    self.case_id,
                    "trabox",
                    step="update_case",
                    screenshots=self._get_screenshot_paths(),
                )
            finally:
                await context.close()
                await browser.close()

    async def delete_case(self, baggage_no: str) -> Dict[str, Any]:
        """登録済み荷物を削除（CRUD の Delete。実環境で検証済み 2026-07-22）

        フロー: ログイン → 登録した荷物一覧 → 対象行の削除ボタン → 確認モーダルで確定
        - 一覧の行は tr[data-row-key='荷物番号'] で一意に特定できる
        - 削除ボタンはツールチップ等に被られるため dispatch_event('click') を使う
        - 確認モーダルは .ant-modal-confirm 内の「削除」ボタン

        Args:
            baggage_no: Trabox の荷物番号（post_case の戻り値 baggage_no）
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()
            self.debug_capture = DebugCapture(page)

            try:
                await self._step_navigate_to_dashboard(page)
                if await self._is_login_page(page):
                    await self._step_login(page)
                    await self._step_navigate_to_dashboard(page)

                # 一覧の描画完了を待機（visible 待ちだと描画遅延で失敗することが
                # あるため DOM 追加時点で先に進む）
                await page.wait_for_selector(
                    "tr[data-row-key]",
                    state="attached",
                    timeout=TRABOX_TIMEOUTS["navigation"],
                )
                await self._dismiss_overlays(page)

                row = page.locator(f"tr[data-row-key='{baggage_no}']")
                if await row.count() != 1:
                    raise ValueError(
                        f"荷物番号 {baggage_no} が一覧に見つかりません"
                        "（既に削除済みか、番号が不正です）"
                    )

                await self.debug_capture.capture_screenshot("delete_before")

                # ツールチップの被りを回避するため click イベントを直接ディスパッチ
                await row.locator("button:has-text('削除')").dispatch_event("click")

                # 確認モーダルで確定
                confirm = page.locator(
                    ".ant-modal-confirm button:has-text('削除')"
                )
                await confirm.first.click(timeout=TRABOX_TIMEOUTS["action"])
                await page.wait_for_timeout(2000)
                await self.debug_capture.capture_screenshot("delete_after")

                # 行が消えたことを確認
                if await row.count() != 0:
                    raise Exception(
                        f"削除後も荷物番号 {baggage_no} が一覧に残っています"
                    )

                logger.info(f"[Trabox] 荷物削除成功: {baggage_no}")
                structured_logger.log_event(
                    "trabox_delete",
                    self.user_id,
                    self.case_id,
                    "trabox",
                    details={"baggage_no": baggage_no},
                )
                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": f"荷物 {baggage_no} を削除しました",
                    "baggage_no": baggage_no,
                }

            except Exception as e:
                raise ErrorHandler.handle_posting_error(
                    e,
                    self.user_id,
                    self.case_id,
                    "trabox",
                    step="delete_case",
                    screenshots=self._get_screenshot_paths(),
                )
            finally:
                await context.close()
                await browser.close()

    async def _dismiss_overlays(self, page: Page) -> None:
        """お知らせモーダル・通知パネル等のオーバーレイを閉じる

        Trabox はログイン後に不定期でお知らせ（.ant-modal-wrap / 通知パネル）を
        表示し、フォーム操作のクリックを遮ることがある。
        """
        try:
            # お知らせパネルの「閉じる」ボタン
            close_btn = page.locator("button:has-text('閉じる')")
            for i in range(await close_btn.count()):
                if await close_btn.nth(i).is_visible():
                    await close_btn.nth(i).click(timeout=3000)
                    logger.info("[Trabox] オーバーレイの「閉じる」をクリック")
                    await page.wait_for_timeout(300)
            # 残っているモーダルは Escape で閉じる
            modal_wrap = page.locator(".ant-modal-wrap")
            for i in range(await modal_wrap.count()):
                if await modal_wrap.nth(i).is_visible():
                    await page.keyboard.press("Escape")
                    logger.info("[Trabox] モーダルを Escape で閉じた")
                    await page.wait_for_timeout(300)
                    break
        except Exception as e:
            logger.debug(f"[Trabox] オーバーレイ処理スキップ: {e}")

    async def _get_registered_baggage_no(self, page: Page) -> Optional[str]:
        """投稿直後に一覧（新着順）の先頭行から荷物番号を取得

        取得失敗しても投稿自体は成功しているため None を返すのみ（非致命）。
        """
        try:
            await page.goto(
                TRABOX_DASHBOARD_URL,
                wait_until="networkidle",
                timeout=TRABOX_TIMEOUTS["navigation"],
            )
            first_row = page.locator("tr[data-row-key]").first
            await first_row.wait_for(
                state="attached", timeout=TRABOX_TIMEOUTS["action"]
            )
            baggage_no = await first_row.get_attribute("data-row-key")
            logger.info(f"[Trabox] 登録された荷物番号: {baggage_no}")
            return baggage_no
        except Exception as e:
            logger.warning(f"[Trabox] 荷物番号の取得に失敗（投稿は成功）: {e}")
            return None

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
            await page.wait_for_load_state("networkidle", timeout=TRABOX_TIMEOUTS["navigation"])
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

        🔴 【重要】このURLのみが正しい登録ページ：
        https://www.trabox.com/baggage/register
        """
        try:
            logger.info("[Trabox] 荷物登録ページにナビゲート中...")
            await self.debug_capture.capture_screenshot("step_3_before_register")

            # 直接URLアクセス（ログイン後のセッション保持）
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

        🔴 Trabox は Ant Design 製 SPA のため、通常の fill/select_option ではなく
        各コンポーネント専用の操作（カレンダー・地図型都道府県・ドロップダウン）を行う。
        必須フィールド（発/着日時・発地/着地・荷姿・運賃）の失敗は投稿全体を失敗させる。
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        try:
            logger.info("[Trabox] フォーム入力中...")

            # フォーム描画完了を待機（SPA のため行構造の出現で判定）
            await page.wait_for_selector(
                ".tbx-form-item", timeout=TRABOX_TIMEOUTS["navigation"]
            )
            await self.debug_capture.capture_screenshot("step_4_form_before_fill")

            D = M.TRABOX_DEFAULTS
            pickup_date = M.parse_date(case_data.get("pickup_date"))
            pickup_time = M.parse_time(case_data.get("pickup_time"))
            pick_pref = M.normalize_prefecture(case_data.get("pick_location", ""))
            drop_pref = M.normalize_prefecture(case_data.get("drop_location", ""))
            pick_city = case_data.get("pick_city") or M.extract_city(
                case_data.get("pick_location", "")
            )
            drop_city = case_data.get("drop_city") or M.extract_city(
                case_data.get("drop_location", "")
            )
            weight_class = M.weight_to_class(case_data.get("cargo_weight"))
            vehicle_option = M.vehicle_to_option(case_data.get("vehicle_type", ""))
            freight = M.format_freight(case_data.get("freight_rate"))
            # --- 拡張キー（未指定なら Trabox 既定値。詳細は TraboxFormMapper 参照） ---
            cargo_type = case_data.get("cargo_type") or D["cargo_type"]
            highway_fee = case_data.get("highway_fee") or D["highway_fee"]
            visibility = case_data.get("visibility") or D["visibility"]
            share = case_data.get("share") or D["share"]
            truck_count = case_data.get("truck_count") or D["truck_count"]
            omakase_billing = case_data.get("omakase_billing") or D["omakase_billing"]
            contact_method = case_data.get("contact_method") or D["contact_method"]
            contact_name = case_data.get("contact_name")  # 指定時のみ担当者を変更
            remarks = case_data.get("remarks")
            # 着日: 未指定なら発日の翌日（翌日着が物流の一般慣行）
            drop_date = M.parse_date(case_data.get("drop_date"))
            # 着時刻: drop_time 指定時は HH:MM、未指定なら「午前」（翌朝着）
            drop_time_parsed = M.parse_time(case_data.get("drop_time"))
            drop_time_labels = (
                list(drop_time_parsed) if drop_time_parsed
                else [D["drop_time_label"]]
            )

            if not pickup_date:
                raise ValueError(f"pickup_date が不正です: {case_data.get('pickup_date')}")
            if not pick_pref or not drop_pref:
                raise ValueError(
                    f"発地/着地が不正です: {case_data.get('pick_location')} → "
                    f"{case_data.get('drop_location')}"
                )
            if not pick_city or not drop_city:
                # Trabox は市区町村が必須（都道府県だけでは登録できない）
                raise ValueError(
                    "Trabox 投稿には市区町村が必須です。発地/着地を"
                    "「東京都港区」のように市区町村まで含めて入力してください "
                    f"（現在: {case_data.get('pick_location')} → "
                    f"{case_data.get('drop_location')}）"
                )
            if not freight:
                raise ValueError(f"freight_rate が不正です: {case_data.get('freight_rate')}")
            if not drop_date:
                drop_date = M.next_day(pickup_date)

            # --- 0. 公開範囲（既定: すべて） ---
            await self._select_radio(page, "公開範囲", visibility)

            # --- 1. 発（日付+時刻）: カレンダードロップダウン ---
            await self._select_datetime(
                page, "発", pickup_date,
                list(pickup_time) if pickup_time else None,
            )
            await self.debug_capture.capture_screenshot("step_4_filled_pickup_datetime")

            # --- 2. 積み時間（フリーテキスト・任意） ---
            if case_data.get("pickup_time"):
                await page.fill(
                    M.PICKUP_TIME_TEXT_SELECTOR,
                    str(case_data["pickup_time"]),
                    timeout=TRABOX_TIMEOUTS["action"],
                )

            # --- 3. 発地（都道府県=地図型 + 市区町村=検索型・両方必須） ---
            await self._select_prefecture(page, "発地", pick_pref)
            await self._select_city(page, "発地", pick_city)
            await self.debug_capture.capture_screenshot("step_4_filled_pick_location")

            # --- 4. 着（日時・必須）: 既定は発日の翌日・午前着（翌朝着の一般慣行） ---
            await self._select_datetime(page, "着", drop_date, drop_time_labels)
            await self.debug_capture.capture_screenshot("step_4_filled_drop_datetime")

            # --- 4b. 卸し時間（フリーテキスト・任意） ---
            if case_data.get("drop_time"):
                await page.fill(
                    M.DROP_TIME_TEXT_SELECTOR,
                    str(case_data["drop_time"]),
                    timeout=TRABOX_TIMEOUTS["action"],
                )

            # --- 5. 着地（都道府県 + 市区町村） ---
            await self._select_prefecture(page, "着地", drop_pref)
            await self._select_city(page, "着地", drop_city)
            await self.debug_capture.capture_screenshot("step_4_filled_drop_location")

            # --- 6. 荷姿（必須ラジオ）: 「その他」選択で荷種等のサブフォームが出現 ---
            await self._select_radio(page, "荷姿", "その他")

            # --- 7. 荷種（荷姿=その他 選択時の必須項目） ---
            # オートコンプリート型（.ant-select-auto-complete）のため search 入力にタイプする
            # 🔴 Escape は入力値ごとクリアされるため使用禁止。Tab でフォーカスを外す
            cargo_input = page.locator(
                f"{M.row_selector('荷種')} input[type='search']"
            ).first
            await cargo_input.click(timeout=TRABOX_TIMEOUTS["action"])
            await cargo_input.fill(cargo_type, timeout=TRABOX_TIMEOUTS["action"])
            await page.wait_for_timeout(300)
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(300)
            # 値が保持されているか検証（AutoComplete はブラー時に消えることがある）
            if not await cargo_input.input_value():
                logger.warning("[Trabox] 荷種が消えたため再入力（Enter確定方式）")
                await cargo_input.click(timeout=TRABOX_TIMEOUTS["action"])
                await cargo_input.fill(cargo_type, timeout=TRABOX_TIMEOUTS["action"])
                await page.wait_for_timeout(300)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(300)

            # --- 8. 総重量（任意・kg）: 実際の荷物重量を記載 ---
            if case_data.get("cargo_weight"):
                try:
                    weight_input = modal.locator(
                        f"{M.row_selector('総重量')} input.ant-input"
                    ).first
                    await weight_input.fill(
                        str(int(float(case_data["cargo_weight"]))),
                        timeout=TRABOX_TIMEOUTS["action"],
                    )
                except Exception as we:
                    logger.warning(f"[Trabox] 総重量の入力に失敗（任意のため続行）: {we}")

            await self.debug_capture.capture_screenshot("step_4_filled_cargo")

            # --- 9. 希望車両: 1つ目=重量クラス、2つ目=車種 ---
            row = page.locator(M.row_selector("希望車両")).first
            await self._select_ant_option(page, row.locator(".ant-select").nth(0), weight_class)
            await self._select_ant_option(page, row.locator(".ant-select").nth(1), vehicle_option)
            await self.debug_capture.capture_screenshot("step_4_filled_vehicle")

            # --- 10. 積合（必須ラジオ・既定: 不可） ---
            await self._select_radio(page, "積合", share)

            # --- 11. 台数（必須・既定: 1） ---
            count_input = page.locator(
                f"{M.row_selector('台数')} input"
            ).first
            await count_input.fill(str(truck_count), timeout=TRABOX_TIMEOUTS["action"])

            # --- 12. 運賃（必須・円税別） ---
            freight_input = page.locator(
                f"{M.row_selector('運賃')} input.ant-input"
            ).first
            await freight_input.fill(freight, timeout=TRABOX_TIMEOUTS["action"])

            # --- 13. 高速代（必須ラジオ・既定: 支払わない） ---
            await self._select_radio(page, "高速代", highway_fee)

            # --- 14. おまかせ請求受入可否（必須ラジオ・既定: 受入不可） ---
            await self._select_radio(page, "おまかせ請求受入可否", omakase_billing)

            # --- 15. 連絡方法（必須ラジオ・既定: 電話で受付） ---
            await self._select_radio(page, "連絡方法", contact_method)

            # --- 16. 備考（任意） ---
            if remarks:
                remarks_input = page.locator(
                    f"{M.row_selector('備考')} textarea"
                ).first
                await remarks_input.fill(str(remarks), timeout=TRABOX_TIMEOUTS["action"])

            # --- 17. 担当者（contact_name 指定時のみ変更。未指定はアカウント既定のまま） ---
            if contact_name:
                await self._set_contact_person(page, str(contact_name))

            await self.debug_capture.capture_screenshot("step_4_form_after_fill")

            structured_logger.log_event(
                "trabox_form_fill",
                self.user_id,
                self.case_id,
                "trabox",
                details={
                    "pickup_date": pickup_date,
                    "drop_date": drop_date,
                    "pick": f"{pick_pref}{pick_city}",
                    "drop": f"{drop_pref}{drop_city}",
                    "weight_class": weight_class,
                    "vehicle": vehicle_option,
                    "freight": freight,
                    "cargo_type": cargo_type,
                    "contact_name": contact_name,
                },
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

    async def _select_datetime(
        self,
        page: Page,
        row_label: str,
        date_str: str,
        time_labels,
        root=None,
    ) -> None:
        """発/着の日時ドロップダウン（.ui-datetime-select）を操作

        クリック → カレンダー（td[title="YYYY-MM-DD"]）で日付選択
        → time_labels のメニュー項目を順にクリック → Escape で閉じる

        time_labels の例:
            ["9時", "00分"]  … 時刻指定
            ["午前"]         … 午前着（時メニューの特殊項目）
            None            … 時刻指定なし

        root: 行を探すスコープ（編集モーダル等）。ドロップダウン自体は body 直下に
              描画されるため常に page から探す。
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M
        import re as _re

        base = root if root is not None else page
        trigger = base.locator(
            f"{M.row_selector(row_label)} .ui-datetime-select"
        ).first
        try:
            await trigger.click(timeout=TRABOX_TIMEOUTS["action"])
        except Exception:
            # お知らせモーダル等に被られた場合はイベント直接ディスパッチで開く
            logger.warning(f"[Trabox] {row_label} 通常クリック失敗 → dispatch_event")
            await trigger.dispatch_event("click")

        # 表示中のカレンダードロップダウンを特定
        dropdown = page.locator(
            f"{M.VISIBLE_DROPDOWN}:has(.datetime-container)"
        ).first
        await dropdown.wait_for(state="visible", timeout=TRABOX_TIMEOUTS["action"])

        # 表示月が違う場合は矢印ボタンで移動（最大12回 = 1年分で打ち切り）
        target_title = M.month_title(date_str)
        for _ in range(12):
            title = (
                await dropdown.locator(".calendar-header__title__text").inner_text()
            ).strip()
            if title == target_title:
                break
            cur = _re.match(r"(\d+)年\s*(\d+)月", title)
            tgt = _re.match(r"(\d+)年\s*(\d+)月", target_title)
            if not cur or not tgt:
                break
            go_next = (int(tgt.group(1)), int(tgt.group(2))) > (
                int(cur.group(1)), int(cur.group(2))
            )
            buttons = dropdown.locator(".calendar-header__button button")
            await buttons.nth(1 if go_next else 0).click()
            await page.wait_for_timeout(200)

        # 日付セルをクリック（過去日等は disabled でクリック不可）
        cell = dropdown.locator(
            f"td.ant-picker-cell[title='{date_str}']"
            ":not(.ant-picker-cell-disabled)"
        )
        await cell.first.click(timeout=TRABOX_TIMEOUTS["action"])
        logger.info(f"[Trabox] {row_label} 日付選択: {date_str}")

        # 時刻メニュー（「9時」「00分」または「午前」「午後」等）
        if time_labels:
            for label in time_labels:
                item = dropdown.locator(
                    ".time-dropdown-menu-item", has_text=_re.compile(f"^{label}$")
                )
                try:
                    await item.first.click(timeout=TRABOX_TIMEOUTS["action"])
                    logger.info(f"[Trabox] {row_label} 時刻選択: {label}")
                except Exception as te:
                    logger.warning(f"[Trabox] {row_label} 時刻選択失敗（{label}）: {te}")

        # ドロップダウンを閉じる
        # 🔴 編集ドロワーのカレンダーは「確定」ボタン付きインライン表示。
        #    Escape で閉じると「入力途中の項目があります」警告モーダルが出るため、
        #    確定ボタンがあればクリック、無ければ（登録ページ）Escape で閉じる
        confirm_btn = dropdown.locator("button:has-text('確定')")
        if await confirm_btn.count() and await confirm_btn.first.is_visible():
            await confirm_btn.first.click(timeout=TRABOX_TIMEOUTS["action"])
            logger.info(f"[Trabox] {row_label} カレンダー確定")
        else:
            await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)

        # 万一「入力途中の項目があります」警告が出た場合は「編集を続ける」で復帰
        warn_continue = page.locator(
            ".ant-modal-wrap:visible button:has-text('編集を続ける')"
        )
        if await warn_continue.count():
            await warn_continue.first.click(timeout=TRABOX_TIMEOUTS["action"])
            logger.info(f"[Trabox] 入力途中警告 → 編集を続けるで復帰")
            await page.wait_for_timeout(300)

    async def _select_prefecture(
        self, page: Page, row_label: str, pref_short: str, root=None
    ) -> None:
        """発地/着地の都道府県を日本地図型ドロップダウンから選択

        地図ボタンは「東京」「大阪」等の短縮表記（北海道のみフル表記）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M
        import re as _re

        base = root if root is not None else page
        select = base.locator(
            f"{M.row_selector(row_label)} .ant-select"
        ).first
        await select.click(timeout=TRABOX_TIMEOUTS["action"])

        panel = page.locator(
            f"{M.VISIBLE_SELECT_DROPDOWN} .ui-prefecture-dropdown-container"
        ).first
        await panel.wait_for(state="visible", timeout=TRABOX_TIMEOUTS["action"])

        # 完全一致で地図ボタンをクリック（「京都」と「東京」の誤マッチ防止）
        button = panel.locator(
            "button.map-button", has_text=_re.compile(f"^{_re.escape(pref_short)}$")
        )
        await button.first.click(timeout=TRABOX_TIMEOUTS["action"])
        logger.info(f"[Trabox] {row_label} 都道府県選択: {pref_short}")
        await page.wait_for_timeout(300)

    async def _select_city(
        self, page: Page, row_label: str, city: str, root=None
    ) -> None:
        """発地/着地の市区町村を検索型ドロップダウンから選択【必須】

        行内2つ目の .ant-select をクリック → 市区町村名をタイプして絞り込み
        → title 完全一致のオプションをクリック（例: title="港区"）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        base = root if root is not None else page
        select = base.locator(
            f"{M.row_selector(row_label)} .ant-select"
        ).nth(1)
        await select.click(timeout=TRABOX_TIMEOUTS["action"])

        dropdown = page.locator(M.VISIBLE_SELECT_DROPDOWN).last
        await dropdown.wait_for(state="visible", timeout=TRABOX_TIMEOUTS["action"])

        # 検索絞り込み（クリックで検索入力にフォーカスが当たる）
        await page.keyboard.type(city)
        await page.wait_for_timeout(500)

        option = dropdown.locator(f".ant-select-item-option[title='{city}']")
        try:
            await option.first.click(timeout=TRABOX_TIMEOUTS["action"])
        except Exception:
            # 完全一致が無い場合は絞り込み結果の先頭を選択
            # （例: 入力「港区芝浦」→ 候補「港区」のような部分一致ケース）
            fallback = dropdown.locator(".ant-select-item-option").first
            fallback_title = await fallback.get_attribute("title")
            logger.warning(
                f"[Trabox] {row_label} 市区町村の完全一致なし: "
                f"{city} → 候補先頭の {fallback_title} を選択"
            )
            await fallback.click(timeout=TRABOX_TIMEOUTS["action"])
        logger.info(f"[Trabox] {row_label} 市区町村選択: {city}")
        await page.wait_for_timeout(300)

    async def _select_ant_option(
        self, page: Page, select_locator, option_text: str
    ) -> None:
        """Ant Design セレクトのドロップダウンから選択肢を完全一致で選ぶ"""
        import re as _re

        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        await select_locator.click(timeout=TRABOX_TIMEOUTS["action"])
        dropdown = page.locator(M.VISIBLE_SELECT_DROPDOWN).last
        await dropdown.wait_for(state="visible", timeout=TRABOX_TIMEOUTS["action"])

        option = dropdown.locator(
            ".ant-select-item-option",
            has_text=_re.compile(f"^{_re.escape(option_text)}$"),
        )
        try:
            await option.first.click(timeout=TRABOX_TIMEOUTS["action"])
            logger.info(f"[Trabox] セレクト選択: {option_text}")
        except Exception as e:
            # 選択肢が見つからない場合は既定値のまま閉じる（問わず等）
            logger.warning(f"[Trabox] 選択肢が見つかりません（{option_text}）: {e}")
            await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)

    async def _select_radio(
        self, page: Page, row_label: str, option_label: str
    ) -> None:
        """行内のラジオボタンをラベルテキストで選択（例: 荷姿 → その他）

        まず完全一致（前後空白許容）で探し、なければ部分一致にフォールバック
        （例:「電話で受付」→「電話で受付（従来通り）」）。
        ⚠️「受入可」のように他の選択肢（受入不可）に包含されるラベルは
        完全一致で解決されるため誤選択しない。
        """
        import re as _re

        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        wrappers = page.locator(
            f"{M.row_selector(row_label)} .ant-radio-wrapper"
        )
        exact = wrappers.filter(
            has_text=_re.compile(rf"^\s*{_re.escape(option_label)}\s*$")
        )
        try:
            await exact.first.click(timeout=TRABOX_TIMEOUTS["action"])
        except Exception:
            partial = wrappers.filter(has_text=option_label)
            await partial.first.click(timeout=TRABOX_TIMEOUTS["action"])
        logger.info(f"[Trabox] {row_label} ラジオ選択: {option_label}")

    async def _set_contact_person(self, page: Page, name: str) -> None:
        """担当者を変更する

        「担当者を変更する」チェック → オートコンプリート入力が有効化されるので
        担当者名をタイプして Tab で確定（荷種と同じ Ant AutoComplete 型）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        checkbox = page.locator(
            ".ant-checkbox-wrapper:has-text('担当者を変更する')"
        ).first
        await checkbox.click(timeout=TRABOX_TIMEOUTS["action"])
        await page.wait_for_timeout(500)

        name_input = page.locator(
            f"{M.row_selector('担当者')} input[type='search']"
        ).first
        await name_input.click(timeout=TRABOX_TIMEOUTS["action"])
        await name_input.fill(name, timeout=TRABOX_TIMEOUTS["action"])
        await page.wait_for_timeout(300)
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(300)
        if not await name_input.input_value():
            logger.warning("[Trabox] 担当者名が消えたため再入力（Enter確定方式）")
            await name_input.click(timeout=TRABOX_TIMEOUTS["action"])
            await name_input.fill(name, timeout=TRABOX_TIMEOUTS["action"])
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)
        logger.info(f"[Trabox] 担当者変更: {name}")

    async def _step_submit_form(self, page: Page) -> None:
        """ステップ 5: フォーム送信"""
        from app.automations.trabox_form_mapper import TraboxFormMapper

        try:
            logger.info("[Trabox] フォーム送信中...")
            await self.debug_capture.capture_screenshot("step_5_before_submit")

            # 送信ボタンをクリック
            submit_selector = TraboxFormMapper.SUBMIT_BUTTON_SELECTOR
            logger.info(f"[Trabox] 送信ボタンをクリック: {submit_selector}")

            await page.click(submit_selector, timeout=TRABOX_TIMEOUTS["action"])
            await self.debug_capture.capture_screenshot("step_5_button_clicked")

            # 確認モーダルが出た場合は確定ボタンをクリック（出ない場合はスキップ）
            try:
                confirm = page.locator(
                    ".ant-modal:visible button.ant-btn-primary"
                ).first
                await confirm.click(timeout=5000)
                logger.info("[Trabox] 確認モーダルで確定をクリック")
                await self.debug_capture.capture_screenshot("step_5_modal_confirmed")
            except Exception:
                logger.debug("[Trabox] 確認モーダルなし（そのまま続行）")

            # 送信後のページ遷移を待機
            logger.info("[Trabox] ページ遷移を待機中...")
            try:
                await page.wait_for_load_state("networkidle", timeout=TRABOX_TIMEOUTS["navigation"])
                await self.debug_capture.capture_screenshot("step_5_after_navigation")
            except Exception as nav_error:
                logger.warning(f"[Trabox] ページ遷移タイムアウト: {nav_error}")
                # ナビゲーションが無い可能性もあるため、少し待機
                await page.wait_for_timeout(2000)
                await self.debug_capture.capture_screenshot("step_5_after_wait")

            # 成功判定
            success = await self._check_submission_success(page)

            if success:
                logger.info("[Trabox] フォーム送信成功を確認しました")
                await self.debug_capture.capture_screenshot("step_5_success_confirmed")
            else:
                logger.error("[Trabox] フォーム送信に失敗したか、成功を確認できませんでした")
                await self.debug_capture.capture_screenshot("step_5_success_uncertain")
                # 失敗した場合はエラーを投げる
                raise Exception("Trabox フォーム送信に失敗しました：成功メッセージが表示されず、URLも遷移していません")

            structured_logger.log_event(
                "trabox_submit",
                self.user_id,
                self.case_id,
                "trabox",
                details={"success": success, "message": "フォーム送信完了"},
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

    async def _check_submission_success(self, page: Page) -> bool:
        """送信成功判定

        成功の判定基準:
        1. 成功メッセージが表示されている
        2. URL が変更された（登録一覧へのリダイレクト等）
        3. エラーメッセージが表示されていない
        """
        try:
            # 成功メッセージをチェック（日本語含む）
            success_patterns = [
                "登録完了",
                "成功",
                "完了しました",
                "荷物情報を登録",
            ]

            for pattern in success_patterns:
                count = await page.locator(f"text='{pattern}'").count()
                if count > 0:
                    logger.info(f"[Trabox] 成功メッセージ確認: {pattern}")
                    return True

            # URL 変更をチェック（登録ページから別ページに遷移）
            current_url = page.url
            if not current_url.endswith("/baggage/register"):
                logger.info(f"[Trabox] URL 変更確認: {current_url}")
                return True

            # エラーメッセージをチェック
            error_patterns = ["エラー", "失敗", "入力してください", "必須項目"]
            for pattern in error_patterns:
                count = await page.locator(f"text='{pattern}'").count()
                if count > 0:
                    logger.error(f"[Trabox] エラーメッセージ検出: {pattern}")
                    return False

            # 判定できない場合は失敗
            logger.warning("[Trabox] 成功判定が不確実です（詳細はスクリーンショット参照）")
            logger.warning(f"[Trabox] URL: {current_url}")
            logger.warning(f"[Trabox] ページコンテンツから成功メッセージが見つかりません")
            return False  # 判定できない場合は失敗と判定

        except Exception as e:
            logger.warning(f"[Trabox] 成功判定エラー: {e}")
            return False  # 判定失敗は失敗と判定

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
        debug_info = (
            ErrorDebugInfo(self.debug_capture).get_debug_info()
            if self.debug_capture
            else {}
        )
        ErrorHandler.log_error_details(
            error,
            structured_logger,
            extra_context={
                "platform": "trabox",
                "debug_info": debug_info,
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
