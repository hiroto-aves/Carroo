"""Trabox 投稿の手動検査スクリプト

実際のブラウザ画面をスクリーンショットして、何が起きているのかを確認
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


async def test_trabox_manual():
    """Trabox に手動で投稿を試みて、各ステップのスクリーンショットを撮影"""

    username = os.getenv("TRABOX_TEST_USERNAME")
    password = os.getenv("TRABOX_TEST_PASSWORD")

    if not username or not password:
        print("❌ 環境変数が設定されていません:")
        print("  export TRABOX_TEST_USERNAME=...")
        print("  export TRABOX_TEST_PASSWORD=...")
        return

    # スクリーンショット保存ディレクトリ
    screenshot_dir = Path("manual_inspection") / datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    print(f"📸 スクリーンショット保存先: {screenshot_dir}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # GUI表示
        page = await browser.new_page()

        try:
            # ステップ 1: ログインページへ
            print("\n📍 ステップ 1: ログインページへ...")
            await page.goto("https://www.trabox.com/baggage/list/opened", timeout=30000)
            await asyncio.sleep(2)
            await page.screenshot(path=screenshot_dir / "01_login_page.png")
            print(f"URL: {page.url}")

            # ステップ 2: ログイン
            print("\n📍 ステップ 2: ログイン...")
            await page.fill("input[name='loginid']", username, timeout=10000)
            await page.fill("input[name='loginpwd']", password, timeout=10000)
            await page.click("span:has-text('ログイン')", timeout=10000)
            await asyncio.sleep(3)
            await page.screenshot(path=screenshot_dir / "02_after_login.png")
            print(f"URL: {page.url}")

            # ステップ 3: 新規登録ボタンをクリック
            print("\n📍 ステップ 3: 新規登録ボタンをクリック...")
            await page.click("a:has-text('新規登録'), button:has-text('新規登録')", timeout=10000)
            await asyncio.sleep(2)
            await page.screenshot(path=screenshot_dir / "03_register_button_clicked.png")
            print(f"URL: {page.url}")

            # ステップ 4: フォームページが表示されたか確認
            print("\n📍 ステップ 4: フォームを確認...")
            await asyncio.sleep(1)
            await page.screenshot(path=screenshot_dir / "04_form_page.png")

            # ページのHTMLを確認
            html = await page.content()
            print(f"\n📋 フォームのHTMLサイズ: {len(html)} bytes")

            # 実際に存在するフォーム要素を調べる
            print("\n🔍 フォーム要素の検査:")
            input_fields = await page.locator("input").count()
            print(f"  input 要素数: {input_fields}")

            selects = await page.locator("select").count()
            print(f"  select 要素数: {selects}")

            # input 要素の name 属性を一覧表示
            print("\n📝 input 要素の name 属性:")
            for i in range(min(input_fields, 20)):
                try:
                    name = await page.locator("input").nth(i).get_attribute("name")
                    type_attr = await page.locator("input").nth(i).get_attribute("type")
                    print(f"   [{i}] name='{name}' type='{type_attr}'")
                except Exception as e:
                    print(f"   [{i}] エラー: {e}")

            # select 要素の name 属性を一覧表示
            print("\n📝 select 要素の name 属性:")
            for i in range(min(selects, 20)):
                try:
                    name = await page.locator("select").nth(i).get_attribute("name")
                    print(f"   [{i}] name='{name}'")
                except Exception as e:
                    print(f"   [{i}] エラー: {e}")

            # ボタン要素を確認
            print("\n📝 ボタン要素:")
            buttons = await page.locator("button").count()
            for i in range(min(buttons, 10)):
                try:
                    text = await page.locator("button").nth(i).text_content()
                    print(f"   [{i}] '{text}'")
                except Exception as e:
                    print(f"   [{i}] エラー: {e}")

            # 1つのフィールドだけ試してみる
            print("\n📍 ステップ 5: 最初のフィールドに入力を試みる...")
            await asyncio.sleep(1)
            await page.screenshot(path=screenshot_dir / "05_before_fill.png")

            # 最初のinputフィールドに入力
            first_inputs = await page.locator("input").count()
            if first_inputs > 0:
                await page.locator("input").first.fill("テスト入力", timeout=5000)
                await asyncio.sleep(1)
                await page.screenshot(path=screenshot_dir / "06_after_fill.png")
                print("✅ 入力完了")

            # ステップ 6: ページコンテンツをファイル保存
            print("\n📍 ステップ 6: ページHTMLを保存...")
            with open(screenshot_dir / "page_html.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ 保存完了: page_html.html")

            print("\n" + "="*80)
            print(f"📸 全スクリーンショット保存完了: {screenshot_dir}")
            print("="*80)

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            await page.screenshot(path=screenshot_dir / "error.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_trabox_manual())
