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
        error_message TEXT,
        FOREIGN KEY(case_id) REFERENCES cases(id)
    )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully!")
