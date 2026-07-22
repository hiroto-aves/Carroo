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

                # 成功ログ
                structured_logger.log_posting_completed(
                    self.user_id,
                    self.case_id,
                    "trabox",
                    {"status": "success", "message": "Trabox への投稿に成功しました"},
                )

                return {
                    "status": "success",
                    "platform": "trabox",
                    "message": "投稿に成功しました",
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
            cargo_type = case_data.get("cargo_type") or M.DEFAULT_CARGO_TYPE
            highway_fee = case_data.get("highway_fee") or M.DEFAULT_HIGHWAY_FEE

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

            # --- 1. 発（日付+時刻）: カレンダードロップダウン ---
            await self._select_datetime(page, "発", pickup_date, pickup_time)
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

            # --- 4. 着（日時・必須）: 着日時データが無いため発日と同日を指定 ---
            await self._select_datetime(page, "着", pickup_date, None)
            await self.debug_capture.capture_screenshot("step_4_filled_drop_datetime")

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
                    weight_input = page.locator(
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

            # --- 10. 運賃（必須・円税別） ---
            freight_input = page.locator(
                f"{M.row_selector('運賃')} input.ant-input"
            ).first
            await freight_input.fill(freight, timeout=TRABOX_TIMEOUTS["action"])

            # --- 11. 高速代（必須ラジオ） ---
            await self._select_radio(page, "高速代", highway_fee)

            await self.debug_capture.capture_screenshot("step_4_form_after_fill")

            structured_logger.log_event(
                "trabox_form_fill",
                self.user_id,
                self.case_id,
                "trabox",
                details={
                    "pickup_date": pickup_date,
                    "pick_pref": pick_pref,
                    "drop_pref": drop_pref,
                    "weight_class": weight_class,
                    "vehicle": vehicle_option,
                    "freight": freight,
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
        time_parts,
    ) -> None:
        """発/着の日時ドロップダウン（.ui-datetime-select）を操作

        クリック → カレンダー（td[title="YYYY-MM-DD"]）で日付選択
        → 時刻指定があれば「H時」「MM分」メニューを選択 → Escape で閉じる
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M
        import re as _re

        trigger = page.locator(
            f"{M.row_selector(row_label)} .ui-datetime-select"
        ).first
        await trigger.click(timeout=TRABOX_TIMEOUTS["action"])

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

        # 時刻メニュー（時→分の順。10分刻み）
        if time_parts:
            hour_label, minute_label = time_parts
            for label in (hour_label, minute_label):
                item = dropdown.locator(
                    ".time-dropdown-menu-item", has_text=_re.compile(f"^{label}$")
                )
                try:
                    await item.first.click(timeout=TRABOX_TIMEOUTS["action"])
                    logger.info(f"[Trabox] {row_label} 時刻選択: {label}")
                except Exception as te:
                    logger.warning(f"[Trabox] {row_label} 時刻選択失敗（{label}）: {te}")

        # ドロップダウンを閉じる
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)

    async def _select_prefecture(
        self, page: Page, row_label: str, pref_short: str
    ) -> None:
        """発地/着地の都道府県を日本地図型ドロップダウンから選択

        地図ボタンは「東京」「大阪」等の短縮表記（北海道のみフル表記）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M
        import re as _re

        select = page.locator(
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
        self, page: Page, row_label: str, city: str
    ) -> None:
        """発地/着地の市区町村を検索型ドロップダウンから選択【必須】

        行内2つ目の .ant-select をクリック → 市区町村名をタイプして絞り込み
        → title 完全一致のオプションをクリック（例: title="港区"）
        """
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        select = page.locator(
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
        """行内のラジオボタンをラベルテキストで選択（例: 荷姿 → その他）"""
        from app.automations.trabox_form_mapper import TraboxFormMapper as M

        radio = page.locator(
            f"{M.row_selector(row_label)} .ant-radio-wrapper:has-text('{option_label}')"
        )
        await radio.first.click(timeout=TRABOX_TIMEOUTS["action"])
        logger.info(f"[Trabox] {row_label} ラジオ選択: {option_label}")

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
