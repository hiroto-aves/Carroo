"""
データベース永続化テスト
SQLite のデータ挿入・取得・永続化を検証
"""

import sqlite3
from datetime import datetime
from app.utils.security import hash_password
import os

DB_FILE = "carroo.db"

def test_user_operations():
    """ユーザー登録・取得テスト"""
    print("\n" + "=" * 80)
    print("【Test 1】ユーザー操作（登録・取得）")
    print("=" * 80)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # テストユーザー登録
        test_username = "test_user_001"
        test_email = f"{test_username}@example.com"
        test_password = "test_password_123"
        hashed_pw = hash_password(test_password)

        print(f"\n【登録】")
        print(f"  Username: {test_username}")
        print(f"  Email: {test_email}")
        print(f"  Password Hash: {hashed_pw[:20]}...")

        cursor.execute(
            """INSERT INTO users (username, email, password, hashed_password, role)
            VALUES (?, ?, ?, ?, ?)""",
            (test_username, test_email, test_password, hashed_pw, "user")
        )
        conn.commit()
        user_id = cursor.lastrowid
        print(f"  ✓ ユーザーID: {user_id}")

        # ユーザー取得
        print(f"\n【取得】")
        cursor.execute(
            "SELECT id, username, email, hashed_password FROM users WHERE id = ?",
            (user_id,)
        )
        user = cursor.fetchone()

        if user:
            print(f"  ✓ ユーザーが見つかりました")
            print(f"    ID: {user[0]}")
            print(f"    Username: {user[1]}")
            print(f"    Email: {user[2]}")
            print(f"    Password Hash: {user[3][:20]}...")
        else:
            print(f"  ✗ ユーザーが見つかりません")
            return False

        return True

    except Exception as e:
        print(f"  ✗ エラー: {e}")
        return False
    finally:
        conn.close()


def test_case_operations():
    """案件登録・取得テスト"""
    print("\n" + "=" * 80)
    print("【Test 2】案件操作（登録・取得）")
    print("=" * 80)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # テスト用ユーザーID（Test 1で作成したユーザーID）
        # 最後に登録されたユーザーを取得
        cursor.execute("SELECT id FROM users ORDER BY id DESC LIMIT 1")
        user_result = cursor.fetchone()
        if not user_result:
            print("  ✗ テスト用ユーザーが見つかりません")
            return False
        user_id = user_result[0]

        # 案件登録
        test_case = {
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

        print(f"\n【登録】")
        for key, value in test_case.items():
            print(f"  {key}: {value}")

        cursor.execute(
            """INSERT INTO cases
            (user_id, pick_location, drop_location, cargo_weight, vehicle_type,
             freight_rate, pickup_date, pickup_time, contact_name, contact_phone, contact_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, test_case["pick_location"], test_case["drop_location"],
             test_case["cargo_weight"], test_case["vehicle_type"],
             test_case["freight_rate"], test_case["pickup_date"],
             test_case["pickup_time"], test_case["contact_name"],
             test_case["contact_phone"], test_case["contact_email"])
        )
        conn.commit()
        case_id = cursor.lastrowid
        print(f"\n  ✓ 案件ID: {case_id}")

        # 案件取得
        print(f"\n【取得】")
        cursor.execute(
            """SELECT id, user_id, pick_location, drop_location, cargo_weight,
                     vehicle_type, freight_rate, pickup_date, created_at
            FROM cases WHERE id = ?""",
            (case_id,)
        )
        case = cursor.fetchone()

        if case:
            print(f"  ✓ 案件が見つかりました")
            print(f"    ID: {case[0]}")
            print(f"    User ID: {case[1]}")
            print(f"    Pick Location: {case[2]}")
            print(f"    Drop Location: {case[3]}")
            print(f"    Weight: {case[4]} kg")
            print(f"    Vehicle Type: {case[5]}")
            print(f"    Freight Rate: ¥{case[6]:,.0f}")
            print(f"    Pickup Date: {case[7]}")
            print(f"    Created At: {case[8]}")
        else:
            print(f"  ✗ 案件が見つかりません")
            return False

        return case_id

    except Exception as e:
        print(f"  ✗ エラー: {e}")
        return False
    finally:
        conn.close()


def test_posting_history(case_id):
    """投稿履歴記録・取得テスト"""
    print("\n" + "=" * 80)
    print("【Test 3】投稿履歴操作（記録・取得）")
    print("=" * 80)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # トラボックス投稿履歴
        print(f"\n【トラボックス投稿記録】")
        cursor.execute(
            """INSERT INTO posting_history
            (case_id, platform, status, error_message)
            VALUES (?, ?, ?, ?)""",
            (case_id, "trabox", "success", None)
        )
        conn.commit()
        print(f"  ✓ トラボックス投稿履歴を記録しました")

        # WebKit 投稿履歴（エラー）
        print(f"\n【WebKit投稿記録（エラー）】")
        cursor.execute(
            """INSERT INTO posting_history
            (case_id, platform, status, error_message)
            VALUES (?, ?, ?, ?)""",
            (case_id, "webkit", "error", "API key not configured")
        )
        conn.commit()
        print(f"  ✓ WebKit投稿履歴を記録しました（エラー）")

        # 投稿履歴取得
        print(f"\n【投稿履歴取得】")
        cursor.execute(
            """SELECT id, case_id, platform, status, posted_at, error_message
            FROM posting_history WHERE case_id = ?
            ORDER BY posted_at DESC""",
            (case_id,)
        )
        histories = cursor.fetchall()

        if histories:
            print(f"  ✓ {len(histories)} 件の投稿履歴が見つかりました")
            for history in histories:
                status_icon = "✓" if history[3] == "success" else "✗"
                print(f"    {status_icon} {history[2]}: {history[3]}")
                if history[5]:
                    print(f"       エラー: {history[5]}")
        else:
            print(f"  ✗ 投稿履歴が見つかりません")
            return False

        return True

    except Exception as e:
        print(f"  ✗ エラー: {e}")
        return False
    finally:
        conn.close()


def show_database_summary():
    """データベースサマリー表示"""
    print("\n" + "=" * 80)
    print("【データベースサマリー】")
    print("=" * 80)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # ユーザー数
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"\n👥 ユーザー総数: {user_count}")

        # 案件数
        cursor.execute("SELECT COUNT(*) FROM cases")
        case_count = cursor.fetchone()[0]
        print(f"📦 案件総数: {case_count}")

        # 投稿履歴
        cursor.execute(
            """SELECT platform, COUNT(*) as count,
                      SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success
            FROM posting_history GROUP BY platform"""
        )
        posting_stats = cursor.fetchall()
        if posting_stats:
            print(f"📊 投稿履歴:")
            for platform, count, success in posting_stats:
                success = success or 0
                print(f"   {platform}: {success}/{count} 成功")

        print("\n✅ データベース永続化テスト完了")

    except Exception as e:
        print(f"  ✗ エラー: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 データベース永続化テストスイート")
    print("=" * 80)

    # Test 1: ユーザー操作
    user_success = test_user_operations()

    # Test 2: 案件操作
    case_id = test_case_operations() if user_success else False

    # Test 3: 投稿履歴
    if case_id:
        history_success = test_posting_history(case_id)
    else:
        history_success = False

    # サマリー表示
    show_database_summary()

    # 結果
    print("\n" + "=" * 80)
    if user_success and case_id and history_success:
        print("✅ すべてのテストが成功しました")
    else:
        print("❌ 一部のテストが失敗しました")
    print("=" * 80)
