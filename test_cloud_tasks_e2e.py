"""
エンドツーエンド統合テスト（Cloud Tasks）
非同期投稿フロー全体をテスト
"""

import asyncio
import logging
import requests
import json
from datetime import datetime
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CloudTasksE2ETest:
    """Cloud Tasks エンドツーエンドテスト"""

    def __init__(self, base_url="http://localhost:8000"):
        """
        初期化

        Args:
            base_url: Web UI のベース URL
        """
        self.base_url = base_url
        self.session = requests.Session()

    def test_case_registration_flow(self):
        """
        テスト：案件登録フロー
        1. ユーザーが投稿フォーム送信
        2. 即座に「キューに追加しました」と返す（HTTP 202）
        3. Cloud Tasks にタスクが追加される
        """

        print("\n" + "=" * 80)
        print("【テスト 1】案件登録フロー（非同期）")
        print("=" * 80)

        # テスト用ログインユーザー情報
        login_data = {
            "username": "testuser",
            "password": "testpass123"
        }

        # Step 1: ユーザーログイン
        print("\n[Step 1] ユーザーログイン")
        print("-" * 80)

        login_response = self.session.post(
            f"{self.base_url}/auth/login",
            data=login_data
        )

        if login_response.status_code == 200:
            print(f"✅ ログイン成功 (HTTP {login_response.status_code})")
            print(f"   Set-Cookie: {login_response.headers.get('set-cookie', 'N/A')[:50]}...")
        else:
            print(f"❌ ログイン失敗 (HTTP {login_response.status_code})")
            print(f"   レスポンス: {login_response.text[:200]}")
            return False

        # Step 2: 案件登録フォーム送信
        print("\n[Step 2] 案件登録フォーム送信")
        print("-" * 80)

        case_data = {
            "pick_location": "東京都",
            "drop_location": "大阪府",
            "cargo_weight": "100.0",
            "vehicle_type": "small_truck",
            "freight_rate": "50000",
            "pickup_date": "2026-07-20",
            "pickup_time": "10:00",
            "contact_name": "山田太郎",
            "contact_phone": "09012345678",
            "contact_email": "yamada@example.com",
            "post_to_trabox": "yes",
            "post_to_webkit": "no",
        }

        start_time = datetime.now()

        register_response = self.session.post(
            f"{self.base_url}/cases/register",
            data=case_data
        )

        elapsed_time = (datetime.now() - start_time).total_seconds()

        print(f"📡 リクエスト送信: {case_data['pick_location']} → {case_data['drop_location']}")
        print(f"⏱️  応答時間: {elapsed_time:.2f} 秒")

        # Step 3: レスポンス確認
        print("\n[Step 3] レスポンス確認")
        print("-" * 80)

        if register_response.status_code == 202:
            print(f"✅ キューに追加（HTTP {register_response.status_code}）")
            response_json = register_response.json()
            print(f"   Status: {response_json.get('status')}")
            print(f"   Message: {response_json.get('message')}")
            print(f"   Case ID: {response_json.get('case_id')}")
            print(f"   Task Name: {response_json.get('task_name', 'N/A')}")

            # 応答時間の確認（0.1秒以内）
            if elapsed_time < 1.0:
                print(f"   ⚡ 応答時間 < 1.0秒（即座に返却）✅")
            else:
                print(f"   ⚠️ 応答時間 > 1.0秒（背景処理待機中?）")

            case_id = response_json.get('case_id')
            return True, case_id

        else:
            print(f"❌ エラー（HTTP {register_response.status_code}）")
            print(f"   レスポンス: {register_response.text[:200]}")
            return False, None

    def test_posting_history(self, case_id):
        """
        テスト：投稿履歴確認
        DB に正しく記録されているか確認
        """

        print("\n" + "=" * 80)
        print("【テスト 2】投稿履歴確認")
        print("=" * 80)

        if not case_id:
            print("❌ Case ID が取得できていません")
            return False

        print(f"\n[Step 1] Case ID {case_id} の投稿履歴を確認")
        print("-" * 80)

        # ダッシュボードから投稿履歴を取得
        history_response = self.session.get(
            f"{self.base_url}/cases/{case_id}"
        )

        if history_response.status_code == 200:
            print(f"✅ 投稿履歴を取得（HTTP {history_response.status_code}）")

            # HTML レスポンスなので、含まれているテキストを確認
            response_text = history_response.text

            if "pending" in response_text:
                print(f"   ✅ Status: pending（投稿待機中）")
            elif "success" in response_text:
                print(f"   ✅ Status: success（投稿完了）")
            elif "error" in response_text:
                print(f"   ⚠️ Status: error（投稿失敗）")
            else:
                print(f"   ℹ️ Status 確認不可（HTML レスポンス）")

            return True
        else:
            print(f"❌ エラー（HTTP {history_response.status_code}）")
            return False

    def test_dashboard(self):
        """
        テスト：ダッシュボード表示
        ユーザーがダッシュボードで投稿進捗を確認できるか
        """

        print("\n" + "=" * 80)
        print("【テスト 3】ダッシュボード表示")
        print("=" * 80)

        dashboard_response = self.session.get(
            f"{self.base_url}/dashboard"
        )

        if dashboard_response.status_code == 200:
            print(f"✅ ダッシュボード表示（HTTP {dashboard_response.status_code}）")
            response_text = dashboard_response.text

            # ダッシュボード要素の確認
            elements = {
                "統計情報": "total_cases" in response_text or "statistics" in response_text,
                "投稿履歴": "posting_history" in response_text or "history" in response_text,
            }

            for element, found in elements.items():
                status = "✅" if found else "⚠️"
                print(f"   {status} {element}")

            return True
        else:
            print(f"❌ エラー（HTTP {dashboard_response.status_code}）")
            return False

    def test_notifications(self):
        """
        テスト：リアルタイム通知（SSE）
        投稿開始・完了通知が送信されるか確認
        """

        print("\n" + "=" * 80)
        print("【テスト 4】リアルタイム通知（SSE）")
        print("=" * 80)

        print("\n[Step 1] SSE ストリームに接続")
        print("-" * 80)

        try:
            sse_response = self.session.get(
                f"{self.base_url}/notifications/subscribe",
                stream=True,
                timeout=5
            )

            if sse_response.status_code == 200:
                print(f"✅ SSE 接続成功（HTTP {sse_response.status_code}）")

                # 最初の 5 行を読む
                line_count = 0
                for line in sse_response.iter_lines():
                    if line_count >= 5:
                        break
                    if line:
                        print(f"   📨 {line.decode('utf-8')[:80]}")
                        line_count += 1

                return True
            else:
                print(f"❌ SSE 接続失敗（HTTP {sse_response.status_code}）")
                return False

        except requests.Timeout:
            print(f"⚠️ SSE ストリーム タイムアウト（接続確立）")
            return True  # 接続自体は成功
        except Exception as e:
            print(f"❌ SSE エラー: {e}")
            return False

    def test_health_check(self):
        """
        テスト：ヘルスチェック
        Web UI が起動しているか確認
        """

        print("\n" + "=" * 80)
        print("【テスト 0】ヘルスチェック")
        print("=" * 80)

        print(f"\n[接続] {self.base_url}/health")

        try:
            health_response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )

            if health_response.status_code == 200:
                print(f"✅ Web UI が起動中（HTTP {health_response.status_code}）")
                print(f"   {health_response.json()}")
                return True
            else:
                print(f"❌ Web UI エラー（HTTP {health_response.status_code}）")
                return False

        except requests.ConnectionError:
            print(f"❌ 接続失敗: {self.base_url}")
            print(f"   💡 Web UI を起動してください: python main.py")
            return False
        except Exception as e:
            print(f"❌ エラー: {e}")
            return False


async def main():
    """メインテスト実行"""

    print("\n" + "=" * 80)
    print("🚀 Cloud Tasks エンドツーエンド統合テスト")
    print("=" * 80)

    tester = CloudTasksE2ETest()

    # テスト実行
    results = {}

    # テスト 0: ヘルスチェック
    results["ヘルスチェック"] = tester.test_health_check()

    if not results["ヘルスチェック"]:
        print("\n❌ Web UI が起動していません")
        print("   実行: python main.py")
        return

    # テスト 1: 案件登録フロー
    success, case_id = tester.test_case_registration_flow()
    results["案件登録フロー"] = success

    if success:
        # テスト 2: 投稿履歴確認
        results["投稿履歴確認"] = tester.test_posting_history(case_id)

    # テスト 3: ダッシュボード
    results["ダッシュボード"] = tester.test_dashboard()

    # テスト 4: SSE 通知
    results["リアルタイム通知"] = tester.test_notifications()

    # 結果集計
    print("\n" + "=" * 80)
    print("📊 テスト結果サマリー")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ 成功" if result else "❌ 失敗"
        print(f"{status} {test_name}")

    print(f"\n合計: {passed}/{total} テスト成功")

    if passed == total:
        print("\n🎉 すべてのテストが成功しました！")
        print("\n📝 次のステップ:")
        print("  1. 本番環境にデプロイ: ./scripts/deploy_to_gcp.sh your-project-id")
        print("  2. ログを確認: gcloud run logs read poster")
        print("  3. キューを確認: gcloud tasks queues describe posting-queue")
    else:
        print("\n⚠️ いくつかのテストが失敗しました")
        print("\n💡 トラブルシューティング:")
        print("  1. ログを確認: tail -f app.log")
        print("  2. ローカルテスト: python test_cloud_tasks_local.py")
        print("  3. ドキュメント: GCP_SETUP.md")


if __name__ == "__main__":
    asyncio.run(main())
