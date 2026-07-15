import sqlite3
import os

# データベースファイルのパスを定義
DATABASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'carroo.db')

def init_db():
    """
    データベースとテーブルを初期化する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # ユーザーテーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # 管理者アカウントを作成（初回のみ）
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ('admin',))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ('admin', 'password', 'admin'))
    
    # 投稿履歴テーブル
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            userid TEXT,
            loading_date TEXT,
            loading_time TEXT,
            loading_time_option TEXT,
            loading_prefecture TEXT,
            loading_city TEXT,
            loading_address TEXT,
            unloading_date TEXT,
            unloading_time TEXT,
            unloading_time_option TEXT,
            unloading_prefecture TEXT,
            unloading_city TEXT,
            unloading_address TEXT,
            package_type TEXT,
            consolidation_item TEXT,
            transport_category TEXT,
            item_shape TEXT,
            weight TEXT,
            vehicle_size TEXT,
            desired_vehicle_type TEXT,
            vehicle_grade TEXT,
            required_equipment TEXT,
            desired_fare TEXT,
            fare_option TEXT,
            toll_fee TEXT,
            insurance TEXT,
            cases TEXT,
            notes TEXT,
            contact_person TEXT,
            phone_number TEXT,
            webkit_status TEXT DEFAULT '未投稿',
            trabox_status TEXT DEFAULT '未投稿'
        )
    ''')
    conn.commit()
    conn.close()

def save_job_history(form_data, userid):
    """
    案件データをデータベースに保存する
    保存成功したデータのidを返す
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO job_history (
            userid,
            loading_date, loading_time, loading_time_option, loading_prefecture, loading_city, loading_address,
            unloading_date, unloading_time, unloading_time_option, unloading_prefecture, unloading_city, unloading_address,
            package_type, consolidation_item, transport_category, item_shape, weight, vehicle_size,
            desired_vehicle_type, vehicle_grade, required_equipment, desired_fare, fare_option,
            toll_fee, insurance, cases, notes, contact_person, phone_number
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        userid,
        form_data['loading_date'], form_data['loading_time'], form_data['loading_time_option'],
        form_data['loading_prefecture'], form_data['loading_city'], form_data['loading_address'],
        form_data['unloading_date'], form_data['unloading_time'], form_data['unloading_time_option'],
        form_data['unloading_prefecture'], form_data['unloading_city'], form_data['unloading_address'],
        form_data['package_type'], form_data['consolidation_item'], form_data['transport_category'],
        form_data['item_shape'], form_data['weight'], form_data['vehicle_size'],
        form_data['desired_vehicle_type'], form_data['vehicle_grade'], form_data['required_equipment'],
        form_data['desired_fare'], form_data['fare_option'],
        form_data['toll_fee'], form_data['insurance'], form_data['cases'], form_data['notes'],
        form_data['contact_person'], form_data['phone_number']
    ))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def update_job_status(job_id, service, status):
    """
    特定の投稿のステータスを更新する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    if service == 'webkit':
        cursor.execute('UPDATE job_history SET webkit_status = ? WHERE id = ?', (status, job_id))
    elif service == 'trabox':
        cursor.execute('UPDATE job_history SET trabox_status = ? WHERE id = ?', (status, job_id))
    conn.commit()
    conn.close()

def get_job_history(username=None, start_date=None, end_date=None, limit=None, offset=None):
    """
    フィルター付きで投稿履歴を取得する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = 'SELECT * FROM job_history WHERE 1=1'
    params = []

    if username:
        query += ' AND userid = ?'
        params.append(username)
    if start_date:
        query += ' AND date(timestamp) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND date(timestamp) <= ?'
        params.append(end_date)
        
    query += ' ORDER BY timestamp DESC'
    if limit is not None and offset is not None:
        query += ' LIMIT ? OFFSET ?'
        params.append(limit)
        params.append(offset)
    
    cursor.execute(query, params)
    history = cursor.fetchall()
    conn.close()
    return history

def get_job_count(username=None, start_date=None, end_date=None):
    """
    フィルター付きで投稿履歴の総件数を取得する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    query = 'SELECT COUNT(*) FROM job_history WHERE 1=1'
    params = []

    if username:
        query += ' AND userid = ?'
        params.append(username)
    if start_date:
        query += ' AND date(timestamp) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND date(timestamp) <= ?'
        params.append(end_date)
        
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

def create_user(username, password, role='user'):
    """
    新しいユーザーを作成する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
    conn.commit()
    conn.close()

def delete_user(username):
    """
    ユーザーを削除する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_all_users():
    """
    すべてのユーザー情報を取得する
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT username, role FROM users')
    users = cursor.fetchall()
    conn.close()
    return users