"""
WebKIT ブラウザ自動ログインテスト
実際のログイン機能の動作確認
"""

import asyncio
import logging
from app.automations.webkit import WebkitAutomation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_webkit_browser_login():
    """WebKIT ブラウザ自動ログインテスト"""

    print("\n" + "=" * 80)
    print("🧪 WebKIT ブラウザ自動ログインテスト")
    print("=" * 80)

    # ログイン情報の確認
    login_id = settings.WEBKIT_LOGIN_ID
    login_password = settings.WEBKIT_LOGIN_PASSWORD

    if not login_id or not login_password:
        print("\n❌ エラー: WebKIT ログイン情報が設定されていません")
        print("   .env ファイルを確認してください：")
        print("   - WEBKIT_LOGIN_ID=your_member_id")
        print("   - WEBKIT_LOGIN_PASSWORD=your_password")
        return False

    print(f"\n✓ ログイン情報が設定されています")
    print(f"  Member ID: {login_id[:5]}***{login_id[-3:]}")
    print(f"  Password: {'*' * len(login_password)}")

    print("\n【ログインテスト実行中】")
    print("-" * 80)

    automation = WebkitAutomation()

    try:
        print("1. WebKIT にログイン中...")
        result = await automation.login_and_post_case({})

        print(f"\n【テスト結果】")
        print("-" * 80)
        print(f"Status: {result['status']}")
        print(f"Platform: {result['platform']}")
        print(f"Message: {result['message']}")

        if result['status'] == 'success':
            print("\n✅ ログインテスト成功！")
            print("   WebKIT への自動ログインが正常に機能しています")
            print("   スクリーンショット: webkit_logged_in.png")
            return True
        else:
            print("\n❌ ログインテスト失敗")
            print(f"   {result['message']}")
            return False

    except Exception as e:
        print(f"\n❌ 例外エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""

    print("\n" + "=" * 80)
    print("🚀 WebKIT ブラウザ自動ログインテストスイート")
    print("=" * 80)

    login_result = await test_webkit_browser_login()

    # 結果まとめ
    print("\n" + "=" * 80)
    print("【テスト完了】")
    print("=" * 80)

    if login_result:
        print("\n🎉 ログインテストが成功しました！")
        print("   WebKIT の自動ログイン機能は正常に動作しています。")
    else:
        print("\n⚠️ ログインテストが失敗しました")
        print("   エラーログとスクリーンショットを確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
