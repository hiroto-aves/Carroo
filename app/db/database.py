import sqlite3
from app.config import settings
import os

DATABASE_FILE = "carroo.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        pick_location TEXT NOT NULL,
        drop_location TEXT NOT NULL,
        cargo_weight REAL NOT NULL,
        vehicle_type TEXT NOT NULL,
        freight_rate REAL NOT NULL,
        pickup_date TEXT NOT NULL,
        pickup_time TEXT,
        contact_name TEXT,
        contact_phone TEXT,
        contact_email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posting_history (
        id INTEGER PRIMARY KEY,
        case_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        error_message TEXT,
        baggage_no TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(id)
    )
    ''')

    # 既存DBへのマイグレーション: baggage_no カラムを追加
    # （Trabox の荷物番号。投稿後の更新・削除＝CRUD に必要）
    cursor.execute("PRAGMA table_info(posting_history)")
    columns = [row[1] for row in cursor.fetchall()]
    if "baggage_no" not in columns:
        cursor.execute(
            "ALTER TABLE posting_history ADD COLUMN baggage_no TEXT"
        )

    # 既存DBへのマイグレーション: cases.extras カラムを追加
    # Trabox フォーム全項目（必要十分条件）のうち基本スキーマ外の拡張キーを
    # JSON で保持する（drop_date / drop_time / cargo_type / highway_fee /
    # omakase_billing / contact_method / truck_count / share / visibility / remarks）
    cursor.execute("PRAGMA table_info(cases)")
    case_columns = [row[1] for row in cursor.fetchall()]
    if "extras" not in case_columns:
        cursor.execute("ALTER TABLE cases ADD COLUMN extras TEXT")

    # 既存DBへのマイグレーション: ユーザーごとの連絡先初期設定
    # （初期設定画面で登録し、案件登録フォームの連絡先に自動入力される）
    cursor.execute("PRAGMA table_info(user_credentials)")
    cred_columns = [row[1] for row in cursor.fetchall()]
    for col in ("contact_name", "contact_phone", "contact_email"):
        if col not in cred_columns:
            cursor.execute(f"ALTER TABLE user_credentials ADD COLUMN {col} TEXT")

    # 既存DBへのマイグレーション: users に is_admin カラムを追加
    # 管理者は全ユーザーの案件閲覧・ユーザー新規登録が可能
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    if "is_admin" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        # 既定ユーザー「管理者」を管理者に昇格
        cursor.execute("UPDATE users SET is_admin = 1 WHERE username = '管理者'")

    # 既存DBへのマイグレーション: posting_history に action カラムを追加
    # 追記式イベントログ化: register(登録) / update(変更) / delete(削除) を
    # 操作のたびに1行ずつ追加する。削除しても登録行は残るため「登録した事実」が保持される。
    cursor.execute("PRAGMA table_info(posting_history)")
    ph_columns = [row[1] for row in cursor.fetchall()]
    if "action" not in ph_columns:
        cursor.execute(
            "ALTER TABLE posting_history ADD COLUMN action TEXT DEFAULT 'register'"
        )
        # 既存行は登録イベントとして扱う
        cursor.execute(
            "UPDATE posting_history SET action = 'register' WHERE action IS NULL"
        )

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posting_batches (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        batch_name TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        scheduled_at TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posting_queue (
        id INTEGER PRIMARY KEY,
        batch_id INTEGER NOT NULL,
        case_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        scheduled_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(batch_id) REFERENCES posting_batches(id),
        FOREIGN KEY(case_id) REFERENCES cases(id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_credentials (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        trabox_username TEXT,
        trabox_password_encrypted TEXT,
        webkit_person_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        UNIQUE(user_id)
    )
    ''')

    conn.commit()
    conn.close()

def update_posting_result(
    case_id: int,
    platform: str,
    status: str,
    baggage_no: str = None,
    error_message: str = None,
    action: str = None,
):
    """投稿完了時に posting_history の pending レコードを結果で更新する

    cases.py の登録エンドポイントは pending 状態で先に記録するため、
    実投稿を行うワーカー（Cloud Tasks → poster）は完了時にこれを呼ぶこと。
    baggage_no は Trabox の荷物番号 / WebKit の伝票番号（CRUD に必要）。

    action を指定した場合は、その action の最新 pending 行を更新する
    （register/update/delete が同一 case×platform に複数あるため取り違え防止）。
    """
    conn = get_db_connection()
    try:
        if action:
            conn.execute(
                """UPDATE posting_history
                SET status = ?, baggage_no = COALESCE(?, baggage_no),
                    error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM posting_history
                    WHERE case_id = ? AND platform = ? AND action = ?
                    ORDER BY id DESC LIMIT 1
                )""",
                (status, baggage_no, error_message, case_id, platform, action),
            )
        else:
            conn.execute(
                """UPDATE posting_history
                SET status = ?, baggage_no = ?, error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id FROM posting_history
                    WHERE case_id = ? AND platform = ?
                    ORDER BY id DESC LIMIT 1
                )""",
                (status, baggage_no, error_message, case_id, platform),
            )
        conn.commit()
    finally:
        conn.close()


def add_posting_event(case_id: int, platform: str, action: str,
                      status: str = "pending") -> int:
    """投稿イベント（登録/変更/削除）を pending で1行追加し、その id を返す

    追記式イベントログ。ワーカーが完了時に update_posting_result(action=...) で
    この行を結果に更新する。
    """
    conn = get_db_connection()
    try:
        cur = conn.execute(
            "INSERT INTO posting_history (case_id, platform, status, action) "
            "VALUES (?, ?, ?, ?)",
            (case_id, platform, status, action),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_active_baggage_no(case_id: int, platform: str) -> str:
    """指定案件×プラットフォームの現在有効な荷物番号/伝票番号を取得

    最新の成功した register または update の baggage_no を返す。
    変更・削除の対象特定に使う。
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT baggage_no FROM posting_history
            WHERE case_id = ? AND platform = ? AND status = 'success'
              AND action IN ('register', 'update') AND baggage_no IS NOT NULL
            ORDER BY id DESC LIMIT 1""",
            (case_id, platform),
        ).fetchone()
        return row[0] if row and row[0] else ""
    finally:
        conn.close()


def get_platform_state(case_id: int, platform: str) -> str:
    """プラットフォームの現在状態を返す: live/deleted/working/error/none

    最新イベントから判定（追記式ログの解釈）。
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            """SELECT action, status FROM posting_history
            WHERE case_id = ? AND platform = ?
            ORDER BY id DESC LIMIT 1""",
            (case_id, platform),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return "none"
    action, status = row[0], row[1]
    if status == "pending":
        return "working"
    if status == "error":
        return "error"
    # success
    if action == "delete":
        return "deleted"
    return "live"  # register / update success


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
