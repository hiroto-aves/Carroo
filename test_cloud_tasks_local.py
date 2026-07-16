"""
ローカル Cloud Tasks テスト
LocalTaskQueue を使用して非同期投稿フローをテスト
（GCP デプロイ前の動作確認用）
"""

import asyncio
import logging
from datetime import datetime
import os
import sys

# 環境変数設定（LocalTaskQueue を使用）
os.environ.pop("GCP_PROJECT_ID", None)

from app.services.cloud_tasks import get_task_client
from app.db.database import get_db_connection, init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_local_task_queue():
    """ローカルタスクキューのテスト"""

    print("\n" + "=" * 80)
    print("🧪 Local Task Queue テスト")
    print("=" * 80)

    # DB 初期化
    init_db()

    # タスククライアント取得（LocalTaskQueue が返される）
    task_client = get_task_client()
    print(f"\n📍 タスククライアント: {type(task_client).__name__}")

    # テスト案件データ
    case_data = {
        "case_id": 1,
        "user_id": 1,
        "pick_location": "東京都",
        "drop_location": "大阪府",
        "cargo_weight": 100.0,
        "vehicle_type": "small_truck",
        "freight_rate": 50000,
        "pickup_date": "2026-07-20",
        "pickup_time": "10:00",
        "contact_name": "山田太郎",
        "contact_phone": "09012345678",
        "contact_email": "yamada@example.com",
        "post_to_trabox": True,
        "post_to_webkit": False,
    }

    print("\n【テスト 1】タスク追加")
    print("-" * 80)
    task_id_1 = task_client.add_posting_task(case_data, user_id=1)
    print(f"✅ タスク 1 追加: {task_id_1}")

    task_id_2 = task_client.add_posting_task(case_data, user_id=1)
    print(f"✅ タスク 2 追加: {task_id_2}")

    task_id_3 = task_client.add_posting_task(case_data, user_id=1)
    print(f"✅ タスク 3 追加: {task_id_3}")

    print("\n【テスト 2】キュー統計")
    print("-" * 80)
    stats = task_client.get_queue_stats()
    print(f"タスク数: {stats['task_count']}")
    print(f"待機中: {stats['pending']}")
    print(f"完了: {stats['completed']}")

    print("\n【テスト 3】投稿処理シミュレーション")
    print("-" * 80)
    print("⏳ 背景で投稿処理が実行されるはずの流れ:")
    print("  1. ユーザーが投稿フォーム送信")
    print("  2. Web UI が即座に「キューに追加しました」と返す")
    print("  3. Cloud Tasks（または LocalTaskQueue）が 1件ずつ処理")
    print("  4. 各タスク内で Playwright が投稿実行")
    print("  5. 結果を DB に記録")
    print("")
    print("✅ Local Task Queue では以下がシミュレートされます:")
    for i, task in enumerate(task_client.tasks, 1):
        print(f"   [{i}] {task['id']}: User {task['user_id']}, Status: {task['status']}")

    print("\n" + "=" * 80)
    print("✅ Local Task Queue テスト完了")
    print("=" * 80)
    print("\n📝 次のステップ:")
    print("  1. 本番環境テスト: export GCP_PROJECT_ID=your-project-id")
    print("  2. デプロイスクリプト実行: ./scripts/deploy_to_gcp.sh your-project-id")
    print("  3. エンドツーエンド統合テスト: test_cloud_tasks_e2e.py")


def test_database_posting_history():
    """DB の posting_history テーブル確認"""

    print("\n" + "=" * 80)
    print("🗄️ Database Posting History テスト")
    print("=" * 80)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # テスト用案件を插入
        print("\n【テスト】案件情報を DB に保存")
        print("-" * 80)

        cursor.execute(
            """INSERT INTO cases
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type, freight_rate, pickup_date, pickup_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (1, "東京都", "大阪府", 100.0, "small_truck", 50000, "2026-07-20", "10:00")
        )
        conn.commit()
        case_id = cursor.lastrowid
        print(f"✅ 案件保存: Case ID {case_id}")

        # posting_history に「pending」を記録
        print("\n【テスト】posting_history に pending ステータスで記録")
        print("-" * 80)

        cursor.execute(
            "INSERT INTO posting_history (case_id, platform, status) VALUES (?, ?, ?)",
            (case_id, "trabox", "pending")
        )
        cursor.execute(
            "INSERT INTO posting_history (case_id, platform, status) VALUES (?, ?, ?)",
            (case_id, "webkit", "pending")
        )
        conn.commit()
        print(f"✅ posting_history に pending 記録")

        # posting_history を確認
        print("\n【テスト】posting_history を確認")
        print("-" * 80)

        cursor.execute("SELECT * FROM posting_history WHERE case_id = ?", (case_id,))
        records = cursor.fetchall()
        for record in records:
            print(f"  Case ID: {record[1]}, Platform: {record[2]}, Status: {record[3]}, Updated: {record[5]}")

        # status を「success」に更新（シミュレーション）
        print("\n【テスト】投稿完了後に status を更新")
        print("-" * 80)

        cursor.execute(
            "UPDATE posting_history SET status = ?, updated_at = ? WHERE case_id = ? AND platform = ?",
            ("success", datetime.now().isoformat(), case_id, "trabox")
        )
        conn.commit()
        print(f"✅ Trabox の status を success に更新")

        # 更新後を確認
        cursor.execute("SELECT * FROM posting_history WHERE case_id = ?", (case_id,))
        records = cursor.fetchall()
        print("\n更新後:")
        for record in records:
            print(f"  Case ID: {record[1]}, Platform: {record[2]}, Status: {record[3]}, Updated: {record[5]}")

        print("\n" + "=" * 80)
        print("✅ Database Posting History テスト完了")
        print("=" * 80)

    except Exception as e:
        print(f"❌ エラー: {e}")
    finally:
        conn.close()


def test_environment_setup():
    """環境変数設定の確認"""

    print("\n" + "=" * 80)
    print("⚙️ 環境変数セットアップテスト")
    print("=" * 80)

    print("\n【確認】必須環境変数")
    print("-" * 80)

    required_vars = {
        "GCP_PROJECT_ID": "GCP プロジェクト ID（本番環境用）",
        "TRABOX_TEST_USERNAME": "トラボックス ユーザー名",
        "TRABOX_TEST_PASSWORD": "トラボックス パスワード",
        "WEBKIT_LOGIN_ID": "WebKIT ログイン ID",
        "WEBKIT_LOGIN_PASSWORD": "WebKIT パスワード",
        "WEBKIT_API_KEY": "WebKIT API キー",
        "WEBKIT_PERSON_ID": "WebKIT 担当者 ID",
    }

    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        status = "✅ 設定済み" if value else "❌ 未設定"
        if value and len(value) > 10:
            display_value = value[:10] + "..."
        else:
            display_value = value or "（未設定）"
        print(f"  {var_name}: {status} ({display_value})")

    print("\n【確認】オプション環境変数")
    print("-" * 80)

    optional_vars = {
        "CLOUD_RUN_URL": "Cloud Run URL（本番環境用）",
        "DATABASE_URL": "データベース URL（デフォルト: ./carroo.db）",
    }

    for var_name, description in optional_vars.items():
        value = os.getenv(var_name)
        status = "✅ 設定済み" if value else "⚪ デフォルト"
        print(f"  {var_name}: {status}")

    print("\n📝 環境変数の設定方法:")
    print("  1. .env ファイルを作成（.env.example をコピー）")
    print("  2. 各環境変数を .env に入力")
    print("  3. 本番環境では GCP_PROJECT_ID を設定して Google Cloud Tasks を使用")


async def main():
    """メインテスト実行"""

    print("\n" + "=" * 80)
    print("🚀 Cloud Tasks ローカルテスト スイート")
    print("=" * 80)

    try:
        test_environment_setup()
        test_local_task_queue()
        test_database_posting_history()

        print("\n" + "=" * 80)
        print("🎉 すべてのテストが完了しました")
        print("=" * 80)
        print("\n📝 次のステップ:")
        print("  1️⃣ ローカル開発: python test_cloud_tasks_local.py")
        print("  2️⃣ 本番デプロイ: ./scripts/deploy_to_gcp.sh <PROJECT_ID>")
        print("  3️⃣ 統合テスト: python test_cloud_tasks_e2e.py")

    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
