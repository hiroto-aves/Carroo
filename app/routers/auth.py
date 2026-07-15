from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from app.models.schemas import UserCreate, User
from app.db.database import get_db_connection
from app.config import settings
import hashlib

router = APIRouter(prefix="/auth", tags=["auth"])

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OneLogi-Post - ログイン</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
                <h1 class="text-2xl font-bold mb-6 text-center">OneLogi-Post</h1>
                <form method="post" action="/auth/login" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-2">ユーザー名</label>
                        <input type="text" name="username" class="w-full px-4 py-2 border rounded" required>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-2">パスワード</label>
                        <input type="password" name="password" class="w-full px-4 py-2 border rounded" required>
                    </div>
                    <button type="submit" class="w-full bg-blue-500 text-white py-2 rounded font-semibold hover:bg-blue-600">
                        ログイン
                    </button>
                </form>
                <p class="text-center mt-4 text-gray-600">
                    アカウントがありません？ <a href="/auth/register" class="text-blue-500 hover:underline">登録する</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

@router.get("/register", response_class=HTMLResponse)
async def register_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OneLogi-Post - 登録</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="min-h-screen flex items-center justify-center">
            <div class="bg-white p-8 rounded-lg shadow-md w-full max-w-sm">
                <h1 class="text-2xl font-bold mb-6 text-center">OneLogi-Post</h1>
                <form method="post" action="/auth/register" class="space-y-4">
                    <div>
                        <label class="block text-gray-700 mb-2">ユーザー名</label>
                        <input type="text" name="username" class="w-full px-4 py-2 border rounded" required>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-2">メールアドレス</label>
                        <input type="email" name="email" class="w-full px-4 py-2 border rounded" required>
                    </div>
                    <div>
                        <label class="block text-gray-700 mb-2">パスワード</label>
                        <input type="password" name="password" class="w-full px-4 py-2 border rounded" required>
                    </div>
                    <button type="submit" class="w-full bg-blue-500 text-white py-2 rounded font-semibold hover:bg-blue-600">
                        登録
                    </button>
                </form>
                <p class="text-center mt-4 text-gray-600">
                    アカウントがありますか？ <a href="/auth/login" class="text-blue-500 hover:underline">ログイン</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

@router.post("/register")
async def register(username: str, email: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        hashed_pw = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            (username, email, hashed_pw)
        )
        conn.commit()

        return {
            "status": "success",
            "message": "User registered successfully"
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    finally:
        conn.close()

@router.post("/login")
async def login(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, email FROM users WHERE username = ? AND hashed_password = ?",
        (username, hash_password(password))
    )

    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            "status": "success",
            "user": {
                "id": user[0],
                "username": user[1],
                "email": user[2]
            }
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
