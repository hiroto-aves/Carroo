"""Trabox フォーム入力E2Eテスト

実ページにログイン → 登録ページ → 全フィールド入力 → スクリーンショット検証
SUBMIT=1 を環境変数に設定した場合のみ登録ボタンを押す（既定は入力のみ）

実行:
    python3 test_trabox_fill_form.py           # 入力のみ（安全）
    SUBMIT=1 python3 test_trabox_fill_form.py  # 実際に登録する
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "trabox_fill_test"
OUT.mkdir(exist_ok=True)

# テスト用案件データ（1ヶ月先の日付を使用すること）
TEST_CASE_DATA = {
    "pick_location": "東京都港区",
    "drop_location": "大阪府大阪市北区",
    "cargo_weight": 1500,           # → 2t クラス
    "vehicle_type": "small_truck",  # → 平
    "freight_rate": 45000,
    "pickup_date": "2026-08-22",    # 8/22 積み
    "pickup_time": "09:00",
    "contact_name": "実験担当",      # 担当者を変更
    # 着日は未指定 → 自動で翌日 8/23 午前着
}


def load_env():
    for line in (Path(__file__).parent / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def main():
    load_env()
    from playwright.async_api import async_playwright
    from app.automations.trabox import TraboxAutomation
    from app.utils.debug_capture import DebugCapture

    submit = os.getenv("SUBMIT") == "1"

    auto = TraboxAutomation(
        user_id=0,
        case_id=0,
        username=os.environ["TRABOX_TEST_USERNAME"],
        password=os.environ["TRABOX_TEST_PASSWORD"],
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 2400})
        page = await context.new_page()
        auto.debug_capture = DebugCapture(page)

        try:
            print("1. ダッシュボードへ...")
            await auto._step_navigate_to_dashboard(page)
            if await auto._is_login_page(page):
                print("2. ログイン実行...")
                await auto._step_login(page)
                await auto._step_navigate_to_dashboard(page)
            print("3. 登録ページへ...")
            await auto._step_navigate_to_register(page)
            print("4. フォーム入力...")
            await auto._step_fill_form(page, TEST_CASE_DATA)
            await page.screenshot(path=str(OUT / "filled_full.png"), full_page=True)
            print(f"✅ 入力完了: {OUT}/filled_full.png")

            if submit:
                print("5. 登録ボタンを押して送信...")
                await auto._step_submit_form(page)
                await page.screenshot(path=str(OUT / "submitted.png"), full_page=True)
                print("✅ 送信完了")

                # 登録した荷物一覧を確認（削除UIの調査用にダンプ）
                print("6. 登録した荷物一覧を確認...")
                await page.goto(
                    "https://www.trabox.com/baggage/list/opened",
                    wait_until="networkidle", timeout=30000,
                )
                await page.wait_for_timeout(2000)
                await page.screenshot(path=str(OUT / "my_listings.png"), full_page=True)
                html = await page.content()
                (OUT / "my_listings.html").write_text(html)
                print(f"✅ 一覧を保存: {OUT}/my_listings.png / .html")
            else:
                print("（登録ボタンは押していません。SUBMIT=1 で送信）")
        except Exception as e:
            await page.screenshot(path=str(OUT / "error_full.png"), full_page=True)
            import traceback
            traceback.print_exc()
            print(f"❌ 失敗: {e}")
        finally:
            await browser.close()


asyncio.run(main())
