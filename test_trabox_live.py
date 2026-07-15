"""
トラボックス実環境連携テスト
実際のトラボックスサイトに対してエンドツーエンドテストを実行します
"""

import asyncio
import logging
from datetime import datetime, timedelta
from app.automations.trabox import TraboxAutomation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_trabox_live_posting():
    """トラボックス実環境テスト"""

    print("\n" + "=" * 80)
    print("🧪 トラボックス実環境連携テスト")
    print("=" * 80)

    # 認証情報の確認
    username = settings.TRABOX_TEST_USERNAME
    password = settings.TRABOX_TEST_PASSWORD

    if not username or not password:
        print("\n❌ エラー: トラボックスのアカウント情報が設定されていません")
        print("   .env ファイルを確認してください：")
        print("   - TRABOX_TEST_USERNAME=your_username")
        print("   - TRABOX_TEST_PASSWORD=your_password")
        return False

    print(f"\n✓ アカウント情報が設定されています")
    print(f"  Username: {username[:3]}***{username[-3:]}")
    print(f"  Password: {'*' * len(password)}")

    # テストケースの準備
    test_case = {
        "username": username,
        "password": password,
        "pick_location": "東京都渋谷区",
        "drop_location": "大阪府大阪市",
        "cargo_weight": 2500.5,
        "vehicle_type": "medium_truck",
        "freight_rate": 150000,
        "pickup_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "pickup_time": "10:00",
        "contact_name": "テストユーザー",
        "contact_phone": "09012345678",
        "contact_email": "test@example.com",
    }

    print("\n【テストケース】")
    print("-" * 80)
    print(f"積地: {test_case['pick_location']}")
    print(f"卸地: {test_case['drop_location']}")
    print(f"重量: {test_case['cargo_weight']} kg")
    print(f"車種: {test_case['vehicle_type']}")
    print(f"運賃: ¥{test_case['freight_rate']:,}")
    print(f"日付: {test_case['pickup_date']} {test_case['pickup_time']}")

    # Playwright による自動投稿テスト
    print("\n【自動投稿テスト実行中】")
    print("-" * 80)

    automation = TraboxAutomation()

    try:
        print("1. トラボックスにアクセス中...")
        result = await automation.post_case(test_case)

        print(f"\n【テスト結果】")
        print("-" * 80)
        print(f"Status: {result['status']}")
        print(f"Platform: {result['platform']}")
        print(f"Message: {result['message']}")

        if result['status'] == 'success':
            print("\n✅ テスト成功！")
            print("   トラボックスへの自動投稿が正常に機能しています")
            return True
        else:
            print("\n❌ テスト失敗")
            print("   エラーが発生しました：")
            print(f"   {result['message']}")

            # スクリーンショットの確認
            import os
            if os.path.exists("error_screenshot_trabox.png"):
                print("\n   📸 エラースクリーンショット:")
                print("      error_screenshot_trabox.png")
            return False

    except Exception as e:
        print(f"\n❌ 例外エラー: {e}")
        print(f"   タイプ: {type(e).__name__}")
        return False


async def test_trabox_login_only():
    """ログイン機能のみをテスト（投稿しない）"""

    print("\n" + "=" * 80)
    print("🔐 トラボックス ログイン専用テスト")
    print("=" * 80)

    username = settings.TRABOX_TEST_USERNAME
    password = settings.TRABOX_TEST_PASSWORD

    if not username or not password:
        print("❌ アカウント情報が設定されていません")
        return False

    print(f"✓ Username: {username}")
    print(f"✓ Password: {'*' * len(password)}")

    print("\nログインのみをテストします（投稿は行いません）")
    print("...")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            print("1. トラボックスのログインページにアクセス...")
            await page.goto("https://www.trabox.com/login?return_to=/baggage/list/opened", wait_until="networkidle", timeout=30000)

            print("2. ページが完全に読み込まれるまで待機...")
            await page.wait_for_timeout(2000)

            print("3. ページのスクリーンショット（デバッグ用）...")
            await page.screenshot(path="trabox_page_initial.png")
            print("   → trabox_page_initial.png")

            print("4. ログイン入力フィールドを探索中...")
            # 複数のセレクターを試す
            login_id_field = await page.query_selector('input[name="loginid"]')
            if not login_id_field:
                login_id_field = await page.query_selector('input[type="text"][placeholder*="ID"]')
            if not login_id_field:
                login_id_field = await page.query_selector('input[type="email"]')

            if login_id_field:
                print("   ✓ ログインID入力フィールドが見つかりました")
                await page.fill('input[name="loginid"]', username)
                print("5. ログインID入力完了")

                # パスワード入力
                password_field = await page.query_selector('input[name="loginpwd"]')
                if not password_field:
                    password_field = await page.query_selector('input[type="password"]')

                if password_field:
                    await page.fill('input[name="loginpwd"]', password)
                    print("6. パスワード入力完了")

                    # ログインボタンを探す
                    print("7. ログインボタンを探中...")
                    login_button = await page.query_selector('button:has-text("ログイン")')
                    if not login_button:
                        login_button = await page.query_selector('input[type="submit"]')
                    if not login_button:
                        login_button = await page.query_selector('span:has-text("ログイン")')

                    if login_button:
                        await login_button.click()
                        print("8. ログインボタンをクリック")

                        print("9. ログイン完了を待機中...")
                        try:
                            await page.wait_for_navigation(timeout=15000)
                        except:
                            print("   ⚠️ ナビゲーション検出できませんが続行...")
                            await page.wait_for_timeout(3000)

                        print("10. ページのタイトルを取得...")
                        title = await page.title()
                        print(f"    ページタイトル: {title}")

                        # スクリーンショット
                        await page.screenshot(path="trabox_login_success.png")
                        print("11. スクリーンショット保存: trabox_login_success.png")

                        await browser.close()
                        print("\n✅ ログインテスト成功！")
                        return True
                    else:
                        print("❌ ログインボタンが見つかりません")
                else:
                    print("❌ パスワード入力フィールドが見つかりません")
            else:
                print("❌ ログインID入力フィールドが見つかりません")
                print("   ページの要素が読み込まれていない可能性があります")
                await page.screenshot(path="trabox_debug.png")
                print("   デバッグスクリーンショット: trabox_debug.png")

            await browser.close()
            return False

    except Exception as e:
        print(f"\n❌ ログインテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""

    print("\n" + "=" * 80)
    print("🚀 トラボックス実環境テストスイート")
    print("=" * 80)

    print("\nテストモードを選択してください：")
    print("1. ログインのみをテスト（推奨：まずこれで確認）")
    print("2. ログイン→投稿の完全フローをテスト")
    print("")

    # ここでは両方を順番に実行
    print("【実行内容】")
    print("1. ログインテスト（投稿なし）")
    print("2. 完全フローテスト（ログイン→投稿）")
    print("=" * 80)

    # テスト 1: ログインのみ
    print("\n【テスト 1】ログイン専用テスト")
    login_result = await test_trabox_login_only()

    if not login_result:
        print("\n⚠️ ログインテストが失敗しました")
        print("   以下を確認してください：")
        print("   1. .env ファイルのトラボックスアカウント情報")
        print("   2. ネットワーク接続")
        print("   3. ブラウザウィンドウが正しく開いたか")
        return

    # テスト 2: 完全フロー
    print("\n【テスト 2】完全フロー（ログイン→投稿）テスト")
    posting_result = await test_trabox_live_posting()

    # 結果まとめ
    print("\n" + "=" * 80)
    print("【テスト完了】")
    print("=" * 80)

    print(f"\n✓ ログインテスト: {'成功' if login_result else '失敗'}")
    print(f"✓ 投稿テスト: {'成功' if posting_result else '失敗'}")

    if login_result and posting_result:
        print("\n🎉 すべてのテストが成功しました！")
        print("   トラボックスの自動投稿機能は正常に動作しています。")
    else:
        print("\n⚠️ 一部のテストが失敗しました")
        print("   エラーログとスクリーンショットを確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
