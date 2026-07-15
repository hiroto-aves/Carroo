"""
データベース検査ユーティリティ
SQLite データベースの内容を表示・エクスポート
"""

import sqlite3
import json
from datetime import datetime
from tabulate import tabulate

DB_FILE = "carroo.db"


def print_section(title):
    """セクション区切り表示"""
    print("\n" + "=" * 80)
    print(f"【{title}】")
    print("=" * 80)


def inspect_users():
    """ユーザーテーブル検査"""
    print_section("ユーザーテーブル（users）")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, username, email, role FROM users ORDER BY id DESC")
        users = cursor.fetchall()

        if users:
            headers = ["ID", "Username", "Email", "Role"]
            rows = []
            for user in users:
                rows.append([
                    user["id"],
                    user["username"],
                    user["email"] or "(未設定)",
                    user["role"] or "(未設定)",
                ])

            print(tabulate(rows, headers=headers, tablefmt="grid"))
            print(f"\n📊 合計: {len(users)} 件")
        else:
            print("データなし")

    except Exception as e:
        print(f"エラー: {e}")
    finally:
        conn.close()


def inspect_cases():
    """案件テーブル検査"""
    print_section("案件テーブル（cases）")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, user_id, pick_location, drop_location, cargo_weight,
                   vehicle_type, freight_rate, pickup_date, created_at
            FROM cases ORDER BY id DESC
        """)
        cases = cursor.fetchall()

        if cases:
            headers = ["ID", "User", "Pick", "Drop", "Weight", "Vehicle", "Fare", "Date"]
            rows = []
            for case in cases:
                rows.append([
                    case["id"],
                    case["user_id"],
                    case["pick_location"][:10],
                    case["drop_location"][:10],
                    f"{case['cargo_weight']:.1f}kg",
                    case["vehicle_type"],
                    f"¥{case['freight_rate']:,.0f}",
                    case["pickup_date"],
                ])

            print(tabulate(rows, headers=headers, tablefmt="grid"))
            print(f"\n📊 合計: {len(cases)} 件")
        else:
            print("データなし")

    except Exception as e:
        print(f"エラー: {e}")
    finally:
        conn.close()


def inspect_posting_history():
    """投稿履歴テーブル検査"""
    print_section("投稿履歴テーブル（posting_history）")

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, case_id, platform, status, posted_at, error_message
            FROM posting_history ORDER BY id DESC
        """)
        histories = cursor.fetchall()

        if histories:
            headers = ["ID", "Case", "Platform", "Status", "Posted At", "Error"]
            rows = []
            for history in histories:
                error_msg = history["error_message"]
                if error_msg and len(error_msg) > 30:
                    error_msg = error_msg[:30] + "..."

                rows.append([
                    history["id"],
                    history["case_id"],
                    history["platform"],
                    history["status"],
                    history["posted_at"][:19] if history["posted_at"] else "",
                    error_msg or "(なし)",
                ])

            print(tabulate(rows, headers=headers, tablefmt="grid"))

            # 統計
            cursor.execute("""
                SELECT platform, COUNT(*) as total,
                       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success
                FROM posting_history GROUP BY platform
            """)
            stats = cursor.fetchall()

            print("\n📊 投稿統計:")
            for stat in stats:
                success = stat[2] or 0
                total = stat[1]
                rate = (success / total * 100) if total > 0 else 0
                print(f"  {stat[0]}: {success}/{total} 成功 ({rate:.0f}%)")
        else:
            print("データなし")

    except Exception as e:
        print(f"エラー: {e}")
    finally:
        conn.close()


def show_database_summary():
    """データベース全体サマリー"""
    print_section("データベースサマリー")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # テーブル一覧
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()

        print("\n📋 テーブル一覧:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  • {table[0]}: {count} 行")

        # ファイルサイズ
        import os
        file_size = os.path.getsize(DB_FILE) / 1024  # KB
        print(f"\n💾 ファイルサイズ: {file_size:.1f} KB")

        # 最終更新
        mod_time = datetime.fromtimestamp(os.path.getmtime(DB_FILE))
        print(f"🕐 最終更新: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"エラー: {e}")
    finally:
        conn.close()


def export_to_json(output_file=None):
    """JSONにエクスポート"""
    if output_file is None:
        output_file = f"db_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        export_data = {}

        # ユーザー
        cursor.execute("SELECT id, username, email, role FROM users")
        export_data["users"] = [dict(row) for row in cursor.fetchall()]

        # 案件
        cursor.execute("SELECT * FROM cases")
        export_data["cases"] = [dict(row) for row in cursor.fetchall()]

        # 投稿履歴
        cursor.execute("SELECT * FROM posting_history")
        export_data["posting_history"] = [dict(row) for row in cursor.fetchall()]

        # ファイル出力
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n✓ {output_file} にエクスポートしました")
        return output_file

    except Exception as e:
        print(f"エラー: {e}")
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🔍 データベース検査ツール")
    print("=" * 80)

    # サマリー
    show_database_summary()

    # テーブル検査
    inspect_users()
    inspect_cases()
    inspect_posting_history()

    # JSON エクスポート
    print("\n" + "=" * 80)
    export_to_json()

    print("\n" + "=" * 80)
    print("✅ 検査完了")
    print("=" * 80 + "\n")
