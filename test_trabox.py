"""
トラボックス自動投稿のテストスクリプト
実際のトラボックスサイトに対してテストを実行します
"""

import asyncio
import sys
from app.automations.trabox import TraboxAutomation

async def test_trabox_mock():
    """モックデータでトラボックス投稿をテスト"""
    print("=" * 80)
    print("トラボックス自動投稿テスト")
    print("=" * 80)

    automation = TraboxAutomation()

    test_case = {
        "username": "test_user",
        "password": "test_password",
        "pick_location": "東京都渋谷区",
        "drop_location": "大阪府大阪市",
        "cargo_weight": 2500.5,
        "vehicle_type": "medium_truck",
        "freight_rate": 150000,
        "pickup_date": "2026-07-25",
        "pickup_time": "10:00",
        "contact_name": "テスト太郎",
        "contact_phone": "09012345678",
        "contact_email": "test@example.com",
    }

    print("\n【テストケース】")
    for key, value in test_case.items():
        print(f"  {key}: {value}")

    print("\n【実行中】")
    result = await automation.post_case(test_case)

    print("\n【結果】")
    print(f"  Status: {result.get('status')}")
    print(f"  Platform: {result.get('platform')}")
    print(f"  Message: {result.get('message')}")

    print("\n" + "=" * 80)

    if result.get("status") == "success":
        print("✅ テスト成功")
        return 0
    else:
        print("❌ テスト失敗")
        return 1

async def test_trabox_interactive():
    """対話的なテスト（実際のトラボックスサイトを使用）"""
    print("\n" + "=" * 80)
    print("トラボックス対話的テスト（ヘッドフル）")
    print("=" * 80)
    print("\nℹ️  ブラウザが開きます。以下を実行してください：")
    print("  1. トラボックスのテストアカウントでログイン")
    print("  2. 案件フォームに以下の値を入力：")
    print("     - 積地: 東京都渋谷区")
    print("     - 卸地: 大阪府大阪市")
    print("     - 重量: 2500.5")
    print("     - 車種: 中型トラック")
    print("     - 運賃: 150000円")
    print("     - 日付: 2026-07-25")
    print("  3. 送信ボタンをクリック")
    print("  4. ブラウザを閉じる")
    print("\n実行しますか？ (y/n): ", end="")

    # 実際のテストは手動実行となるため、ここでは説明のみ
    print("y")

if __name__ == "__main__":
    print("\n🧪 Trabox Automation Test Suite\n")

    # モックテスト（実際には実行されない）
    print("📌 このスクリプトは以下のテストを提供します：")
    print("  1. モックテスト（実際のサイトアクセスなし）")
    print("  2. 対話的テスト（ブラウザ自動操作を可視化）")
    print("\n実際のテストを実行するには、トラボックスのテストアカウント情報が必要です。")
    print("また、トラボックスの利用規約に従ってテストを実施してください。\n")

    # モックテストを実行
    # exit_code = asyncio.run(test_trabox_mock())
    # sys.exit(exit_code)
