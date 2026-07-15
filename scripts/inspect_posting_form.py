"""
トラボックスの投稿フォーム要素を検査するスクリプト
投稿フォームのセレクターを特定します
"""

import asyncio
import sys
from app.config import settings
from playwright.async_api import async_playwright


async def inspect_posting_form():
    """投稿フォームのHTML構造を検査"""

    print("\n" + "=" * 80)
    print("🔍 トラボックス投稿フォーム検査")
    print("=" * 80)

    username = settings.TRABOX_TEST_USERNAME
    password = settings.TRABOX_TEST_PASSWORD

    if not username or not password:
        print("❌ アカウント情報が設定されていません")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("\n【Step 1】ログインページにアクセス...")
            login_url = "https://www.trabox.com/login?return_to=/baggage/register"
            await page.goto(login_url, wait_until="networkidle")
            print(f"✓ {login_url}")

            print("\n【Step 2】ログイン情報を入力...")
            # ログインID
            login_id_field = page.locator('input[name="loginid"]')
            await login_id_field.fill(username)
            print(f"✓ ログインID入力: {username[:10]}...")

            # パスワード
            login_pwd_field = page.locator('input[name="loginpwd"]')
            await login_pwd_field.fill(password)
            print(f"✓ パスワード入力")

            print("\n【Step 3】ログインボタンをクリック...")
            login_btn = page.locator('button:has-text("ログイン")')
            if await login_btn.count() == 0:
                login_btn = page.locator('span:has-text("ログイン")')
            await login_btn.click()
            print("✓ クリック完了")

            print("\n【Step 4】ページの読み込み完了を待機...")
            await page.wait_for_timeout(3000)
            try:
                await page.wait_for_navigation(timeout=5000)
            except:
                pass

            # スクリーンショット
            await page.screenshot(path="scripts/posting_form_initial.png")
            print("✓ スクリーンショット保存: scripts/posting_form_initial.png")

            # ページのURL確認
            current_url = page.url
            print(f"\n【現在のURL】: {current_url}")

            # ページのタイトル確認
            title = await page.title()
            print(f"【ページタイトル】: {title}")

            # 入力フィールドを検査
            print("\n【Step 5】入力フィールドを検査...")
            print("-" * 80)

            # すべての input 要素を取得
            inputs = await page.locator('input').all()
            print(f"\n📝 INPUT 要素 (全 {len(inputs)} 個):")
            for i, inp in enumerate(inputs):
                input_type = await inp.get_attribute("type")
                input_name = await inp.get_attribute("name")
                input_id = await inp.get_attribute("id")
                input_placeholder = await inp.get_attribute("placeholder")
                print(f"  [{i}] type={input_type}, name={input_name}, id={input_id}, placeholder={input_placeholder}")

            # すべての select 要素を取得
            selects = await page.locator('select').all()
            print(f"\n📝 SELECT 要素 (全 {len(selects)} 個):")
            for i, sel in enumerate(selects):
                sel_name = await sel.get_attribute("name")
                sel_id = await sel.get_attribute("id")
                options = await sel.locator('option').all()
                print(f"  [{i}] name={sel_name}, id={sel_id}, options={len(options)}")
                for j, opt in enumerate(options[:5]):  # 最初の5つのみ表示
                    opt_text = await opt.text_content()
                    print(f"      - {opt_text}")

            # すべての button 要素を取得
            buttons = await page.locator('button').all()
            print(f"\n📝 BUTTON 要素 (全 {len(buttons)} 個):")
            for i, btn in enumerate(buttons[:10]):  # 最初の10個のみ表示
                btn_text = await btn.text_content()
                btn_type = await btn.get_attribute("type")
                btn_id = await btn.get_attribute("id")
                btn_name = await btn.get_attribute("name")
                print(f"  [{i}] text={btn_text.strip()}, type={btn_type}, id={btn_id}, name={btn_name}")

            # label 要素を検査
            labels = await page.locator('label').all()
            print(f"\n📝 LABEL 要素 (全 {len(labels)} 個):")
            for i, lbl in enumerate(labels[:10]):
                lbl_text = await lbl.text_content()
                lbl_for = await lbl.get_attribute("for")
                print(f"  [{i}] text={lbl_text.strip()}, for={lbl_for}")

            # フォーム要素を検査
            forms = await page.locator('form').all()
            print(f"\n📝 FORM 要素 (全 {forms} 個):")
            if forms:
                form_action = await forms[0].get_attribute("action")
                form_method = await forms[0].get_attribute("method")
                print(f"  [0] action={form_action}, method={form_method}")

            print("\n【検査完了】")
            print("=" * 80)
            print("✅ フォーム要素の情報を取得しました")
            print("   スクリーンショット: scripts/posting_form_initial.png")

        except Exception as e:
            print(f"\n❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="scripts/posting_form_error.png")
            print("   エラースクリーンショット: scripts/posting_form_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_posting_form())
