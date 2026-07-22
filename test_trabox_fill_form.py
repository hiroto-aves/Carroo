"""Trabox フォーム入力E2Eテスト（登録ボタンは押さない）

実ページにログイン → 登録ページ → 全フィールド入力 → フルページスクリーンショットで検証
実行: python3 test_trabox_fill_form.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OUT = Path(__file__).parent / "trabox_fill_test"
OUT.mkdir(exist_ok=True)


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

    auto = TraboxAutomation(
        user_id=0,
        case_id=0,
        username=os.environ["TRABOX_TEST_USERNAME"],
        password=os.environ["TRABOX_TEST_PASSWORD"],
    )

    case_data = {
        "pick_location": "東京都港区",
        "drop_location": "大阪府大阪市北区",
        "cargo_weight": 1500,       # → 2t クラス
        "vehicle_type": "small_truck",  # → 平
        "freight_rate": 45000,
        "pickup_date": "2026-07-25",
        "pickup_time": "09:00",
    }

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
            await auto._step_fill_form(page, case_data)
            await page.screenshot(path=str(OUT / "filled_full.png"), full_page=True)
            print(f"✅ 入力完了。スクリーンショット: {OUT}/filled_full.png")
            print("（登録ボタンは押していません）")
        except Exception as e:
            await page.screenshot(path=str(OUT / "error_full.png"), full_page=True)
            import traceback
            traceback.print_exc()
            print(f"❌ 失敗: {e}")
        finally:
            await browser.close()


asyncio.run(main())
