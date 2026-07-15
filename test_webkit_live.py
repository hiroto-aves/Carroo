"""
WebKIT API 実環境テスト
実際のWebKIT APIサーバーに対してエンドツーエンドテストを実行します
"""

import asyncio
import logging
from datetime import datetime, timedelta
from app.automations.webkit import WebkitAutomation
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_webkit_live_posting():
    """WebKIT API 実環境テスト"""

    print("\n" + "=" * 80)
    print("🧪 WebKIT API 実環境テスト")
    print("=" * 80)

    # API設定の確認
    api_key = settings.WEBKIT_API_KEY
    person_id = settings.WEBKIT_PERSON_ID

    if not api_key or not person_id:
        print("\n❌ エラー: WebKIT APIの設定が不足しています")
        print("   .env ファイルを確認してください：")
        print("   - WEBKIT_API_KEY=your_20_digit_key")
        print("   - WEBKIT_PERSON_ID=your_14_digit_id")
        return False

    print(f"\n✓ API設定が確認されました")
    print(f"  API Key: {api_key[:5]}***{api_key[-5:]}")
    print(f"  Person ID: {person_id[:5]}***{person_id[-5:]}")

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

    # WebKIT API テスト実行
    print("\n【API投稿テスト実行中】")
    print("-" * 80)

    automation = WebkitAutomation()

    try:
        print("1. WebKIT APIに接続中...")
        result = await automation.post_case(test_case)

        print(f"\n【テスト結果】")
        print("-" * 80)
        print(f"Status: {result['status']}")
        print(f"Platform: {result['platform']}")
        print(f"Message: {result['message']}")

        if 'response_text' in result:
            print(f"Response Preview: {result['response_text']}")

        if 'details' in result:
            print(f"Error Details: {result['details']}")

        if result['status'] == 'success':
            print("\n✅ テスト成功！")
            print("   WebKIT APIへの投稿が正常に機能しています")
            return True
        else:
            print("\n❌ テスト失敗")
            print("   エラーが発生しました：")
            print(f"   {result['message']}")
            if 'details' in result:
                print(f"   詳細: {result['details']}")
            return False

    except Exception as e:
        print(f"\n❌ 例外エラー: {e}")
        print(f"   タイプ: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


async def test_webkit_xml_generation():
    """WebKIT XML生成テスト（API送信なし、XMLの検証のみ）"""

    print("\n" + "=" * 80)
    print("📋 WebKIT XML生成テスト")
    print("=" * 80)

    test_case = {
        "pick_location": "東京都渋谷区",
        "drop_location": "大阪府大阪市",
        "cargo_weight": 2500.5,
        "vehicle_type": "medium_truck",
        "pickup_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
    }

    print("\n【XMLペイロード生成】")
    print("-" * 80)

    automation = WebkitAutomation()

    try:
        xml_data = automation._build_load_registration_xml(test_case)
        xml_str = xml_data.decode('utf-8')

        print("✓ XML生成成功")
        print("\n【生成されたXML】")
        print("-" * 80)
        print(xml_str)
        print("-" * 80)

        # XML構造の検証
        from xml.etree.ElementTree import fromstring
        root = fromstring(xml_str)

        print("\n【XML構造検証】")
        webkit = root.find('webkit')
        if webkit is not None:
            apikey = webkit.find('apikey')
            personid = webkit.find('personid')
            operation = webkit.find('operation')

            print(f"✓ API Key設定: {'✅' if apikey is not None and apikey.text else '❌'}")
            print(f"✓ Person ID設定: {'✅' if personid is not None and personid.text else '❌'}")
            print(f"✓ Operation設定: {'✅' if operation is not None and operation.text == 'I' else '❌'}")

            load_data = webkit.find('load_data')
            if load_data is not None:
                tsumichi = load_data.find('tsumichi_code')
                oroshichi = load_data.find('oroshichi_code')
                weight = load_data.find('weight')

                print(f"✓ 積地コード: {'✅' if tsumichi is not None and tsumichi.text else '❌'}")
                print(f"✓ 卸地コード: {'✅' if oroshichi is not None and oroshichi.text else '❌'}")
                print(f"✓ 重量: {'✅' if weight is not None and weight.text else '❌'}")

        print("\n✅ XML構造検証完了")
        return True

    except Exception as e:
        print(f"\n❌ XML生成エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """メイン処理"""

    print("\n" + "=" * 80)
    print("🚀 WebKIT API テストスイート")
    print("=" * 80)

    print("\n【実行内容】")
    print("1. XML生成テスト（検証のみ）")
    print("2. 実環境API投稿テスト")
    print("=" * 80)

    # テスト 1: XML生成テスト
    print("\n【テスト 1】XML生成テスト")
    xml_result = await test_webkit_xml_generation()

    # テスト 2: 実環境API投稿テスト
    print("\n【テスト 2】実環境API投稿テスト")
    posting_result = await test_webkit_live_posting()

    # 結果まとめ
    print("\n" + "=" * 80)
    print("【テスト完了】")
    print("=" * 80)

    print(f"\n✓ XML生成テスト: {'成功' if xml_result else '失敗'}")
    print(f"✓ API投稿テスト: {'成功' if posting_result else '失敗'}")

    if xml_result and posting_result:
        print("\n🎉 すべてのテストが成功しました！")
        print("   WebKIT APIの自動投稿機能は正常に動作しています。")
    else:
        print("\n⚠️ 一部のテストが失敗しました")
        if not xml_result:
            print("   - XML生成に問題があります")
        if not posting_result:
            print("   - API接続またはレスポンス処理に問題があります")
            print("   - API キー・Person IDを確認してください")


if __name__ == "__main__":
    asyncio.run(main())
