"""
WebKIT API 自動投稿のテストスクリプト
"""

import asyncio
from app.automations.webkit import WebkitAutomation
from datetime import datetime, timedelta
from xml.etree.ElementTree import fromstring, indent

async def test_webkit_xml_generation():
    """WebKIT APIのXML生成をテスト"""
    print("=" * 80)
    print("WebKIT API XML生成テスト")
    print("=" * 80)

    automation = WebkitAutomation()
    automation.api_key = "12345678901234567890"
    automation.person_id = "00000000000001"

    test_case = {
        "pick_location": "東京都",
        "drop_location": "大阪府",
        "cargo_weight": 2500.5,
        "vehicle_type": "small_truck",
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

    print("\n【生成されたXML】")
    xml_data = automation._build_load_registration_xml(test_case)
    xml_str = xml_data.decode('utf-8')

    # XML整形
    try:
        root = fromstring(xml_str)
        indent(root, space="  ")
        from xml.etree.ElementTree import tostring
        formatted = tostring(root, encoding='unicode')
        print(formatted)
    except:
        print(xml_str)

    print("\n" + "=" * 80)

async def test_webkit_api():
    """WebKIT API呼び出しをテスト（実際のAPI）"""
    print("\n" + "=" * 80)
    print("WebKIT API 呼び出しテスト")
    print("=" * 80)

    automation = WebkitAutomation()

    # テストデータ
    test_case = {
        "pick_location": "東京都",
        "drop_location": "大阪府",
        "cargo_weight": 2500,
        "vehicle_type": "small_truck",
        "freight_rate": 150000,
        "pickup_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
    }

    print("\n【リクエスト情報】")
    print(f"  Endpoint: {automation.api_url}")
    print(f"  Method: POST")
    print(f"  Content-Type: application/xml")
    print(f"  API Key: {automation.api_key[:5]}{'*' * 15 if automation.api_key else '(not set)'}")
    print(f"  Person ID: {automation.person_id if automation.person_id else '(not set)'}")

    if not automation.api_key or not automation.person_id:
        print("\n⚠️  APIキーまたは担当者IDが設定されていません")
        print("以下の手順で設定してください：")
        print("  1. WebKIT公式ページから APIキー (20桁) を取得")
        print("  2. WebKIT公式ページから 担当者ID (14桁) を取得")
        print("  3. .env ファイルに以下を設定：")
        print("     WEBKIT_API_KEY=12345678901234567890")
        print("     WEBKIT_PERSON_ID=00000000000001")
        return

    print("\n【実行中】")
    result = await automation.post_case(test_case)

    print("\n【結果】")
    print(f"  Status: {result.get('status')}")
    print(f"  Platform: {result.get('platform')}")
    print(f"  Message: {result.get('message')}")
    if 'response_text' in result:
        print(f"  Response: {result.get('response_text')}")
    if 'details' in result:
        print(f"  Details: {result.get('details')[:200]}")

if __name__ == "__main__":
    print("\n🧪 WebKit API Test Suite\n")

    # XML生成テスト
    asyncio.run(test_webkit_xml_generation())

    # API呼び出しテスト
    asyncio.run(test_webkit_api())
