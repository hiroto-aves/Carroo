from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.routers import auth, cases, dashboard, notifications, settings
from app.db.database import init_db, get_db_connection
from app.utils.security import hash_password
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(
    title="Carroo",
    description="物流案件一括一元投稿アプリ",
    version="0.1.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(settings.router)

@app.on_event("startup")
async def startup_event():
    init_db()

    # デフォルトユーザーを作成（存在しない場合）
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE username = ?", ("管理者",))
        existing_user = cursor.fetchone()

        if not existing_user:
            hashed_pw = hash_password("12341234@")
            cursor.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                ("管理者", "hrt_takeuchi@takeuchiunso.com", hashed_pw)
            )
            conn.commit()
            logging.info("✅ デフォルトユーザー（管理者）を作成しました")
        else:
            logging.info("✅ デフォルトユーザー（管理者）は既に存在します")
    except Exception as e:
        logging.error(f"❌ デフォルトユーザー作成エラー: {e}")
        conn.rollback()
    finally:
        conn.close()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Carroo</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md">
                <h1 class="text-3xl font-bold text-center mb-4">Carroo</h1>
                <p class="text-gray-600 text-center mb-6">物流案件一括一元投稿アプリ</p>
                <a href="/auth/login" class="block bg-blue-500 text-white py-2 px-4 rounded text-center hover:bg-blue-600">ログイン</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Carroo backend is running"}
