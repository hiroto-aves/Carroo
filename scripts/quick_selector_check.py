"""
トラボックス投稿フォームのセレクター素早いチェック
"""

import asyncio
from app.config import settings
from playwright.async_api import async_playwright


async def quick_check():
    username = settings.TRABOX_TEST_USERNAME
    password = settings.TRABOX_TEST_PASSWORD

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # ログインページにアクセス（投稿フォームにリダイレクト）
            print("1. ログインページにアクセス...")
            await page.goto("https://www.trabox.com/login?return_to=/baggage/register", wait_until="networkidle")

            # ログイン
            print("2. ログイン実行中...")
            await page.fill('input[name="loginid"]', username)
            await page.fill('input[name="loginpwd"]', password)
            await page.click('button:has-text("ログイン")')

            # ナビゲーション完了を待機
            print("3. ページ読み込み中...")
            await page.wait_for_timeout(5000)

            # 現在のURL
            current_url = page.url
            print(f"\n✓ 現在のURL: {current_url}")

            # セレクターのテスト
            print("\n【入力フィールドのテスト】")

            # すべての input を調査
            inputs = page.locator("input")
            input_count = await inputs.count()
            print(f"  Input 要素数: {input_count}")

            for i in range(min(input_count, 5)):
                inp = inputs.nth(i)
                inp_type = await inp.get_attribute("type")
                inp_name = await inp.get_attribute("name")
                inp_id = await inp.get_attribute("id")
                inp_placeholder = await inp.get_attribute("placeholder")
                print(f"    [{i}] type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

            # スクリーンショット
            await page.screenshot(path="scripts/quick_check.png")
            print("\n✓ スクリーンショット: scripts/quick_check.png")

        except Exception as e:
            print(f"❌ エラー: {e}")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(quick_check())
