"""
複数プラットフォーム同時投稿テスト
トラボックス・WebKIT 両方のプラットフォームへ同時に投稿
"""

import asyncio
import logging
from datetime import datetime, timedelta
from app.automations.trabox import TraboxAutomation
from app.automations.webkit import WebkitAutomation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_multi_platform_posting():
    """複数プラットフォーム同時投稿テスト"""

    print("\n" + "=" * 80)
    print("🚀 複数プラットフォーム同時投稿テスト")
    print("=" * 80)

    # 認証情報の確認
    print("\n【認証情報確認】")
    print("-" * 80)

    # トラボックス
    trabox_ready = settings.TRABOX_TEST_USERNAME and settings.TRABOX_TEST_PASSWORD
    print(f"🔐 トラボックス: {'✅ 設定済み' if trabox_ready else '❌ 未設定'}")
    if trabox_ready:
        print(f"   Username: {settings.TRABOX_TEST_USERNAME[:10]}***")

    # WebKIT
    webkit_ready = settings.WEBKIT_LOGIN_ID and settings.WEBKIT_LOGIN_PASSWORD
    print(f"🔐 WebKIT: {'✅ 設定済み' if webkit_ready else '❌ 未設定'}")
    if webkit_ready:
        print(f"   Member ID: {settings.WEBKIT_LOGIN_ID[:5]}***")

    if not trabox_ready or not webkit_ready:
        print("\n❌ 両方のプラットフォーム認証情報が必要です")
        return False

    # テストケースの準備
    test_case = {
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

    print("\n【同時投稿実行中】")
    print("-" * 80)

    results = []

    # Trabox 投稿タスク
    async def post_to_trabox():
        print("1️⃣ トラボックスに投稿中...")
        case_data = test_case.copy()
        case_data["username"] = settings.TRABOX_TEST_USERNAME
        case_data["password"] = settings.TRABOX_TEST_PASSWORD

        automation = TraboxAutomation()
        result = await automation.post_case(case_data)
        return ("trabox", result)

    # WebKIT 投稿タスク
    async def post_to_webkit():
        print("2️⃣ WebKIT に投稿中...")
        automation = WebkitAutomation()
        result = await automation.post_case(test_case)
        return ("webkit", result)

    # 並行実行
    try:
        tasks = [post_to_trabox(), post_to_webkit()]
        results = await asyncio.gather(*tasks)

        print("\n【投稿結果】")
        print("-" * 80)

        all_success = True
        for platform, result in results:
            status = "✅" if result["status"] == "success" else "❌"
            print(f"\n{status} {platform.upper()}")
            print(f"   Status: {result['status']}")
            print(f"   Message: {result['message']}")

            if result["status"] != "success":
                all_success = False
                if "details" in result:
                    print(f"   Details: {result['details']}")

        print("\n" + "=" * 80)
        print("【テスト完了】")
        print("=" * 80)

        if all_success:
            print("\n🎉 複数プラットフォームへの同時投稿が成功しました！")
            print("   両方のプラットフォームに案件が登録されました。")
            return True
        else:
            print("\n⚠️ 一部のプラットフォームで投稿に失敗しました")
            return False

    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""
    result = await test_multi_platform_posting()
    return result


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
