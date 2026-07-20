"""Trabox 正しい投稿フロー

メニューの「荷物登録」からアクセス
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright


async def test_correct_flow():
    """正しいフローでTrabox投稿"""

    username = os.getenv("TRABOX_TEST_USERNAME")
    password = os.getenv("TRABOX_TEST_PASSWORD")

    if not username or not password:
        print("❌ 環境変数が設定されていません")
        return

    screenshot_dir = Path("trabox_correct_flow") / datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            # ステップ 1: ログイン
            print("\n📍 ステップ 1: ログイン")
            await page.goto("https://www.trabox.com/baggage/list/opened", timeout=30000)
            await page.fill("input[name='loginid']", username, timeout=10000)
            await page.fill("input[name='loginpwd']", password, timeout=10000)
            await page.click("span:has-text('ログイン')", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            print(f"✅ ログイン完了: {page.url}")

            # ステップ 2: 「荷物登録」メニューをクリック
            print("\n📍 ステップ 2: 「荷物登録」メニューをクリック")

            # 方法1: data-menu-id でクリック
            try:
                await page.click("[data-menu-id='baggageRegister']", timeout=5000)
                print("✅ メニュークリック成功 (data-menu-id)")
            except:
                # 方法2: テキストで検索
                try:
                    await page.click("text=荷物登録", timeout=5000)
                    print("✅ メニュークリック成功 (テキスト)")
                except Exception as e:
                    print(f"❌ メニュークリック失敗: {e}")

            # ページ遷移待機
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
            print(f"✅ ナビゲート完了: {page.url}")

            # スクリーンショット
            await page.screenshot(path=screenshot_dir / "01_after_click_menu.png")
            print(f"📸 スクリーンショット保存")

            # ページのHTMLを保存
            html = await page.content()
            with open(screenshot_dir / "register_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"📄 HTML保存完了 ({len(html)} bytes)")

            # フォーム要素を検査
            print("\n📋 フォーム要素を検査:")
            inputs = await page.locator("input").count()
            selects = await page.locator("select").count()
            textareas = await page.locator("textarea").count()
            buttons = await page.locator("button, input[type='submit']").count()

            print(f"  input: {inputs} 個")
            print(f"  select: {selects} 個")
            print(f"  textarea: {textareas} 個")
            print(f"  button: {buttons} 個")

            # ボタンを表示
            if buttons > 0:
                print("\n📝 ボタン一覧:")
                btns = await page.locator("button, input[type='submit']").all()
                for i, btn in enumerate(btns[:15]):
                    try:
                        text = await btn.text_content()
                        type_attr = await btn.get_attribute("type")
                        print(f"  [{i}] type='{type_attr}' text='{text.strip()}'")
                    except:
                        pass

            # 成功メッセージ（ステップタイトル等）を確認
            print("\n📝 ページタイトル:")
            title = await page.title()
            print(f"  <title>: {title}")

            h1s = await page.locator("h1, h2, .page-title, [class*='title']").all()
            for h in h1s[:5]:
                try:
                    text = await h.text_content()
                    if text.strip():
                        print(f"  見出し: {text.strip()}")
                except:
                    pass

            print("\n" + "="*80)
            print(f"✅ 検査完了: {screenshot_dir}")
            print(f"   URL: {page.url}")
            print(f"   投稿フォームが表示されたか確認してください")
            print("="*80)

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=screenshot_dir / "error.png")
            except:
                pass

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_correct_flow())
