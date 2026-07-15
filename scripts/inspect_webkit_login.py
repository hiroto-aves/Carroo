"""
WebKIT ログインページの要素検査スクリプト
ログイン画面の入力フィールドを特定します
"""

import asyncio
from playwright.async_api import async_playwright


async def inspect_webkit_login():
    """WebKIT のログインページを検査"""

    print("\n" + "=" * 80)
    print("🔍 WebKIT ログインページ検査")
    print("=" * 80)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # WebKIT のメインページにアクセス
            print("\n1. WebKIT メインページにアクセス...")
            await page.goto("https://www.wkit.jp", wait_until="networkidle")
            print(f"   URL: {page.url}")
            print(f"   Title: {await page.title()}")

            # スクリーンショット
            await page.screenshot(path="scripts/webkit_main.png")
            print("   ✓ スクリーンショット: scripts/webkit_main.png")

            # ログインリンクを探す
            print("\n2. ログインリンクを探索...")
            login_links = page.locator("a:has-text('ログイン')")
            login_count = await login_links.count()
            print(f"   ログインリンク検出数: {login_count}")

            if login_count > 0:
                # 最初のログインリンクをクリック
                await login_links.first.click()
                await page.wait_for_timeout(2000)
                print(f"   ✓ ログインリンクをクリック")
                print(f"   現在のURL: {page.url}")

            # スクリーンショット
            await page.screenshot(path="scripts/webkit_login_page.png")
            print("   ✓ スクリーンショット: scripts/webkit_login_page.png")

            # ログインフォームの要素を検査
            print("\n3. ログインフォーム要素を検査...")

            # INPUT 要素を取得
            inputs = await page.locator("input").all()
            print(f"\n   【INPUT 要素】 (全 {len(inputs)} 個)")
            for i, inp in enumerate(inputs[:10]):
                inp_type = await inp.get_attribute("type")
                inp_name = await inp.get_attribute("name")
                inp_id = await inp.get_attribute("id")
                inp_placeholder = await inp.get_attribute("placeholder")
                print(f"     [{i}] type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

            # BUTTON 要素を取得
            buttons = await page.locator("button").all()
            print(f"\n   【BUTTON 要素】 (全 {len(buttons)} 個)")
            for i, btn in enumerate(buttons[:10]):
                btn_text = await btn.text_content()
                btn_type = await btn.get_attribute("type")
                btn_id = await btn.get_attribute("id")
                print(f"     [{i}] text={btn_text.strip()}, type={btn_type}, id={btn_id}")

            # LABEL 要素を取得
            labels = await page.locator("label").all()
            print(f"\n   【LABEL 要素】 (全 {len(labels)} 個)")
            for i, lbl in enumerate(labels[:10]):
                lbl_text = await lbl.text_content()
                lbl_for = await lbl.get_attribute("for")
                print(f"     [{i}] text={lbl_text.strip()}, for={lbl_for}")

            # FORM 要素を取得
            forms = await page.locator("form").all()
            print(f"\n   【FORM 要素】 (全 {len(forms)} 個)")
            if forms:
                form_action = await forms[0].get_attribute("action")
                form_method = await forms[0].get_attribute("method")
                form_id = await forms[0].get_attribute("id")
                print(f"     [0] action={form_action}, method={form_method}, id={form_id}")

            print("\n4. ページのHTML構造を保存...")
            page_content = await page.content()
            with open("scripts/webkit_login_html.txt", "w", encoding="utf-8") as f:
                f.write(page_content)
            print("   ✓ HTML保存: scripts/webkit_login_html.txt")

            print("\n【検査完了】")
            print("=" * 80)
            print("✅ WebKIT ログインページの情報を取得しました")

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="scripts/webkit_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_webkit_login())
