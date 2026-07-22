from fastapi import APIRouter, HTTPException, status, Response, Depends, Form, Cookie
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
        <title>Carroo - ログイン</title>
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
                    <h1 class="text-3xl font-bold text-gray-900">Carroo</h1>
                    <p class="text-gray-600 text-sm mt-2">物流案件一括投稿アプリ</p>
                </div>

                <!-- ログインフォーム -->
                <div class="bg-white rounded-2xl shadow-lg p-8 border border-gray-100">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">ログイン</h2>

                    <div id="error-message" class="hidden mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"></div>

                    <form id="login-form" class="space-y-5">
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

                    <!-- アカウント発行は管理者が行う方針のため、公開の新規登録リンクは無し -->
                    <p class="text-center text-sm text-gray-500 mt-6">
                        アカウントが必要な場合は管理者にお問い合わせください
                    </p>
                </div>

                <!-- フッター -->
                <p class="text-center text-xs text-gray-500 mt-8">
                    © 2026 Carroo. All rights reserved.
                </p>
            </div>
        </div>

        <script>
            document.getElementById('login-form').addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = new FormData(e.target);
                const errorDiv = document.getElementById('error-message');

                try {
                    const response = await fetch('/auth/login', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        // ログイン成功 → ダッシュボードにリダイレクト
                        window.location.href = '/dashboard/';
                    } else {
                        // エラー表示
                        errorDiv.textContent = data.detail || 'ログインに失敗しました';
                        errorDiv.classList.remove('hidden');
                    }
                } catch (error) {
                    errorDiv.textContent = 'エラーが発生しました: ' + error.message;
                    errorDiv.classList.remove('hidden');
                }
            });
        </script>
    </body>
    </html>
    """

@router.get("/register")
async def register_page():
    """公開の新規登録画面は廃止。ログイン画面へ誘導。"""
    return RedirectResponse(url="/auth/login", status_code=302)


async def _register_page_unused():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carroo - 新規登録</title>
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
                    <h1 class="text-3xl font-bold text-gray-900">Carroo</h1>
                    <p class="text-gray-600 text-sm mt-2">物流案件一括投稿アプリ</p>
                </div>

                <!-- 登録フォーム -->
                <div class="bg-white rounded-2xl shadow-lg p-8 border border-gray-100">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">新規登録</h2>

                    <div id="error-message" class="hidden mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"></div>
                    <div id="success-message" class="hidden mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700"></div>

                    <form id="register-form" class="space-y-5">
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
                    © 2026 Carroo. All rights reserved.
                </p>
            </div>
        </div>

        <script>
            document.getElementById('register-form').addEventListener('submit', async (e) => {
                e.preventDefault();

                const formData = new FormData(e.target);
                const errorDiv = document.getElementById('error-message');
                const successDiv = document.getElementById('success-message');

                // エラーと成功メッセージをリセット
                errorDiv.classList.add('hidden');
                successDiv.classList.add('hidden');

                try {
                    const response = await fetch('/auth/register', {
                        method: 'POST',
                        body: formData
                    });

                    const data = await response.json();

                    if (response.ok) {
                        // 登録成功
                        successDiv.textContent = '登録成功！ ログイン画面にリダイレクトしています...';
                        successDiv.classList.remove('hidden');

                        setTimeout(() => {
                            window.location.href = '/auth/login';
                        }, 2000);
                    } else {
                        // エラー表示
                        errorDiv.textContent = data.detail || '登録に失敗しました';
                        errorDiv.classList.remove('hidden');
                    }
                } catch (error) {
                    errorDiv.textContent = 'エラーが発生しました: ' + error.message;
                    errorDiv.classList.remove('hidden');
                }
            });
        </script>
    </body>
    </html>
    """

@router.post("/register")
async def register_disabled():
    """公開の新規登録は無効。アカウント発行は管理者のユーザー管理画面から行う。"""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="新規登録は停止しています。アカウントは管理者が発行します。",
    )

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...), response: Response = None):
    if response is None:
        response = Response()

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

@router.get("/logout")
async def logout_link():
    """ナビの「ログアウト」リンク（GET）用: Cookie を消してログイン画面へ"""
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@router.get("/me", response_class=HTMLResponse)
async def profile_page(access_token: str = Cookie(None)):
    """プロフィールページ（HTML）

    未ログイン時は JSON エラーではなくログイン画面へリダイレクトする。
    JSON が必要な場合は /auth/api/me を使用。
    """
    from app.utils.security import decode_access_token

    # 未ログイン・トークン失効ならログイン画面へ
    token_data = decode_access_token(access_token) if access_token else None
    user_id = token_data.get("user_id") if token_data else None
    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    conn = get_db_connection()
    user = conn.execute(
        "SELECT username, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    username, email, created_at = user[0], user[1], user[2]
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carroo - プロフィール</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80 transition">📦 Carroo</a>
                <div class="flex items-center gap-4">
                    <a href="/dashboard/" class="text-gray-600 hover:text-blue-600 transition">ダッシュボード</a>
                    <a href="/auth/logout" class="text-red-600 hover:text-red-700">ログアウト</a>
                </div>
            </div>
        </div>
    </nav>

    <div class="max-w-2xl mx-auto px-4 py-12">
        <h1 class="text-3xl font-bold text-gray-900 mb-8">プロフィール</h1>
        <div class="bg-white rounded-2xl shadow-lg p-8 space-y-6">
            <div class="flex items-center gap-4 pb-6 border-b">
                <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-3xl">👤</div>
                <div>
                    <p class="text-xl font-bold text-gray-900">{username}</p>
                    <p class="text-gray-500">{email}</p>
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div class="p-4 bg-gray-50 rounded-lg">
                    <p class="text-gray-500 mb-1">ユーザー名</p>
                    <p class="font-semibold text-gray-900">{username}</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-lg">
                    <p class="text-gray-500 mb-1">メールアドレス</p>
                    <p class="font-semibold text-gray-900">{email}</p>
                </div>
                <div class="p-4 bg-gray-50 rounded-lg md:col-span-2">
                    <p class="text-gray-500 mb-1">登録日</p>
                    <p class="font-semibold text-gray-900">{created_at or "-"}</p>
                </div>
            </div>
            <div class="flex gap-4 pt-4">
                <a href="/settings/" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-6 rounded-lg transition">⚙ 初期設定を編集</a>
                <a href="/cases/register" class="bg-gray-100 hover:bg-gray-200 text-gray-900 font-semibold py-2.5 px-6 rounded-lg transition">案件登録へ</a>
            </div>
        </div>
    </div>
</body>
</html>"""


@router.get("/api/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """現在のユーザー情報（JSON API）"""
    return current_user
