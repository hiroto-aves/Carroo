from fastapi import APIRouter, HTTPException, status, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models.schemas import UserCreate, User
from app.db.database import get_db_connection
from app.config import settings
from app.utils.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OneLogi-Post - ログイン</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-br from-blue-50 via-white to-blue-50 min-h-screen">
        <div class="min-h-screen flex items-center justify-center px-4 py-8">
            <div class="w-full max-w-md">
                <!-- ヘッダー -->
                <div class="text-center mb-8">
                    <div class="inline-flex items-center justify-center w-14 h-14 rounded-full bg-blue-600 mb-4">
                        <span class="text-white text-xl font-bold">📦</span>
                    </div>
                    <h1 class="text-3xl font-bold text-gray-900">OneLogi-Post</h1>
                    <p class="text-gray-600 text-sm mt-2">物流案件一括投稿アプリ</p>
                </div>

                <!-- ログインフォーム -->
                <div class="bg-white rounded-2xl shadow-lg p-8 border border-gray-100">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">ログイン</h2>

                    <form method="post" action="/auth/login" class="space-y-5">
                        <!-- ユーザー名 -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                ユーザー名
                            </label>
                            <input
                                type="text"
                                name="username"
                                class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="ユーザー名を入力"
                                required
                            >
                        </div>

                        <!-- パスワード -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                パスワード
                            </label>
                            <input
                                type="password"
                                name="password"
                                class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="パスワードを入力"
                                required
                            >
                        </div>

                        <!-- ログインボタン -->
                        <button
                            type="submit"
                            class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition duration-200 mt-6"
                        >
                            ログイン
                        </button>
                    </form>

                    <!-- リンク -->
                    <p class="text-center text-sm text-gray-600 mt-6">
                        アカウントがありません？
                        <a href="/auth/register" class="text-blue-600 hover:text-blue-700 font-semibold">
                            登録する
                        </a>
                    </p>
                </div>

                <!-- フッター -->
                <p class="text-center text-xs text-gray-500 mt-8">
                    © 2026 OneLogi-Post. All rights reserved.
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
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OneLogi-Post - 新規登録</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-br from-blue-50 via-white to-blue-50 min-h-screen">
        <div class="min-h-screen flex items-center justify-center px-4 py-8">
            <div class="w-full max-w-md">
                <!-- ヘッダー -->
                <div class="text-center mb-8">
                    <div class="inline-flex items-center justify-center w-14 h-14 rounded-full bg-blue-600 mb-4">
                        <span class="text-white text-xl font-bold">📦</span>
                    </div>
                    <h1 class="text-3xl font-bold text-gray-900">OneLogi-Post</h1>
                    <p class="text-gray-600 text-sm mt-2">物流案件一括投稿アプリ</p>
                </div>

                <!-- 登録フォーム -->
                <div class="bg-white rounded-2xl shadow-lg p-8 border border-gray-100">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">新規登録</h2>

                    <form method="post" action="/auth/register" class="space-y-5">
                        <!-- ユーザー名 -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                ユーザー名
                            </label>
                            <input
                                type="text"
                                name="username"
                                class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="ユーザー名を入力"
                                required
                            >
                            <p class="text-xs text-gray-500 mt-1">3〜20文字で入力してください</p>
                        </div>

                        <!-- メールアドレス -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                メールアドレス
                            </label>
                            <input
                                type="email"
                                name="email"
                                class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="example@domain.com"
                                required
                            >
                        </div>

                        <!-- パスワード -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                パスワード
                            </label>
                            <input
                                type="password"
                                name="password"
                                class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="パスワードを入力"
                                required
                            >
                            <p class="text-xs text-gray-500 mt-1">8文字以上で入力してください</p>
                        </div>

                        <!-- 登録ボタン -->
                        <button
                            type="submit"
                            class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 rounded-lg transition duration-200 mt-6"
                        >
                            登録
                        </button>
                    </form>

                    <!-- リンク -->
                    <p class="text-center text-sm text-gray-600 mt-6">
                        既にアカウントをお持ちの方は
                        <a href="/auth/login" class="text-blue-600 hover:text-blue-700 font-semibold">
                            ログイン
                        </a>
                    </p>
                </div>

                <!-- フッター -->
                <p class="text-center text-xs text-gray-500 mt-8">
                    © 2026 OneLogi-Post. All rights reserved.
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
            "message": "User registered successfully. Please login."
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
async def login(username: str, password: str, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, email, hashed_password FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(password, user[3]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token_expires = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    access_token = create_access_token(
        data={"user_id": user[0], "username": user[1]},
        expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )

    return {
        "status": "success",
        "user": {
            "id": user[0],
            "username": user[1],
            "email": user[2]
        },
        "message": "Login successful"
    }

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user
