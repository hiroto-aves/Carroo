"""ユーザー設定ルーター"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from app.utils.encryption import encrypt_password, decrypt_password
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/settings", tags=["settings"])


class CredentialsInput(BaseModel):
    trabox_username: str = None
    trabox_password: str = None
    webkit_api_key: str = None
    webkit_person_id: str = None


@router.get("/", response_class=HTMLResponse)
async def settings_page(current_user: dict = Depends(get_current_user)):
    """設定ページ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]
    username = current_user["username"]

    # 認証情報を取得
    cursor.execute(
        "SELECT trabox_username, webkit_person_id FROM user_credentials WHERE user_id = ?",
        (user_id,)
    )
    creds = cursor.fetchone()
    trabox_username = creds[0] if creds and creds[0] else ""
    webkit_person_id = creds[1] if creds and creds[1] else ""

    conn.close()

    html_template = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carroo - 初期設定</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <!-- ナビゲーションバー -->
        <nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16 items-center">
                    <div class="flex items-center">
                        <a href="/dashboard/" class="text-2xl font-bold text-blue-600">📦 Carroo</a>
                    </div>
                    <div class="flex items-center gap-6">
                        <div class="text-right">
                            <p class="text-sm text-gray-600">ログイン中:</p>
                            <p class="font-semibold text-gray-900">{username}</p>
                        </div>
                        <div class="w-px h-8 bg-gray-300"></div>
                        <a href="/dashboard/" class="text-gray-600 hover:text-blue-600 transition">ダッシュボード</a>
                        <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
                    </div>
                </div>
            </div>
        </nav>

        <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <!-- ページタイトル -->
            <div class="mb-8">
                <h1 class="text-3xl font-bold text-gray-900">初期設定</h1>
                <p class="text-gray-600 mt-2">Trabox と WebKit の認証情報を登録してください</p>
            </div>

            <!-- 設定フォーム -->
            <div class="bg-white rounded-lg shadow-md p-8">
                <form id="settings-form" class="space-y-8">
                    <!-- エラーメッセージ -->
                    <div id="error-message" class="hidden p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"></div>
                    <div id="success-message" class="hidden p-4 bg-green-50 border border-green-200 rounded-lg text-green-700"></div>

                    <!-- Trabox セクション -->
                    <div class="border-b pb-8">
                        <h2 class="text-xl font-semibold text-gray-900 mb-6">🚚 Trabox 認証情報</h2>

                        <div class="space-y-5">
                            <!-- ユーザー名 -->
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">
                                    ユーザー名（メールアドレス）
                                </label>
                                <input
                                    type="email"
                                    name="trabox_username"
                                    id="trabox_username"
                                    class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                    placeholder="example@domain.com"
                                    value="{trabox_username}"
                                >
                                <p class="text-xs text-gray-500 mt-1">Trabox のログインメールアドレス</p>
                            </div>

                            <!-- パスワード -->
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">
                                    パスワード
                                </label>
                                <input
                                    type="password"
                                    name="trabox_password"
                                    id="trabox_password"
                                    class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                    placeholder="パスワードを入力"
                                >
                                <p class="text-xs text-gray-500 mt-1">※ サーバーに暗号化して保存されます</p>
                            </div>
                        </div>
                    </div>

                    <!-- WebKit セクション -->
                    <div class="border-b pb-8">
                        <h2 class="text-xl font-semibold text-gray-900 mb-6">🌐 WebKit API 認証情報</h2>

                        <div class="space-y-5">
                            <!-- API Key -->
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">
                                    API キー（20桁）
                                </label>
                                <input
                                    type="password"
                                    name="webkit_api_key"
                                    id="webkit_api_key"
                                    class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition font-mono"
                                    placeholder="20桁のAPIキー"
                                    maxlength="20"
                                >
                                <p class="text-xs text-gray-500 mt-1">※ サーバーに暗号化して保存されます</p>
                            </div>

                            <!-- 担当者ID -->
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">
                                    担当者 ID（14桁）
                                </label>
                                <input
                                    type="text"
                                    name="webkit_person_id"
                                    id="webkit_person_id"
                                    class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition font-mono"
                                    placeholder="14桁の担当者ID"
                                    value="{webkit_person_id}"
                                    maxlength="14"
                                >
                                <p class="text-xs text-gray-500 mt-1">例: 12345678901234</p>
                            </div>
                        </div>
                    </div>

                    <!-- 保存ボタン -->
                    <div class="flex gap-4">
                        <button
                            type="submit"
                            class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-6 rounded-lg transition duration-200"
                        >
                            保存する
                        </button>
                        <a
                            href="/dashboard/"
                            class="bg-gray-300 hover:bg-gray-400 text-gray-900 font-semibold py-2.5 px-6 rounded-lg transition duration-200"
                        >
                            キャンセル
                        </a>
                    </div>
                </form>
            </div>

            <!-- セキュリティ情報 -->
            <div class="mt-8 p-6 bg-blue-50 border border-blue-200 rounded-lg">
                <h3 class="text-lg font-semibold text-blue-900 mb-3">🔒 セキュリティについて</h3>
                <ul class="text-sm text-blue-800 space-y-2">
                    <li>✅ パスワードはサーバーに暗号化して保存されます</li>
                    <li>✅ API キーは暗号化されます</li>
                    <li>✅ HTTPS で通信されます</li>
                    <li>✅ 投稿時のみに復号化して使用されます</li>
                </ul>
            </div>
        </div>

        <script>
            document.getElementById('settings-form').addEventListener('submit', async (e) => {
                e.preventDefault();

                const errorDiv = document.getElementById('error-message');
                const successDiv = document.getElementById('success-message');

                errorDiv.classList.add('hidden');
                successDiv.classList.add('hidden');

                const formData = new FormData(e.target);
                const data = {
                    trabox_username: formData.get('trabox_username') || null,
                    trabox_password: formData.get('trabox_password') || null,
                    webkit_api_key: formData.get('webkit_api_key') || null,
                    webkit_person_id: formData.get('webkit_person_id') || null,
                };

                try {
                    const response = await fetch('/api/settings/credentials', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });

                    const result = await response.json();

                    if (response.ok) {
                        successDiv.textContent = '✅ 設定を保存しました！';
                        successDiv.classList.remove('hidden');

                        setTimeout(() => {
                            window.location.href = '/dashboard/';
                        }, 2000);
                    } else {
                        errorDiv.textContent = result.detail || '保存に失敗しました';
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

    return html_template.format(
        username=username,
        trabox_username=trabox_username,
        webkit_person_id=webkit_person_id
    )


@router.post("/api/settings/credentials")
async def save_credentials(
    credentials: CredentialsInput,
    current_user: dict = Depends(get_current_user)
):
    """認証情報を保存"""
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]

    try:
        # 暗号化
        trabox_password_encrypted = (
            encrypt_password(credentials.trabox_password)
            if credentials.trabox_password
            else None
        )
        webkit_api_key_encrypted = (
            encrypt_password(credentials.webkit_api_key)
            if credentials.webkit_api_key
            else None
        )

        # 既存のデータを確認
        cursor.execute(
            "SELECT id FROM user_credentials WHERE user_id = ?",
            (user_id,)
        )
        existing = cursor.fetchone()

        if existing:
            # UPDATE
            cursor.execute("""
                UPDATE user_credentials
                SET trabox_username = COALESCE(?, trabox_username),
                    trabox_password_encrypted = COALESCE(?, trabox_password_encrypted),
                    webkit_api_key_encrypted = COALESCE(?, webkit_api_key_encrypted),
                    webkit_person_id = COALESCE(?, webkit_person_id),
                    updated_at = ?
                WHERE user_id = ?
            """, (
                credentials.trabox_username,
                trabox_password_encrypted,
                webkit_api_key_encrypted,
                credentials.webkit_person_id,
                datetime.utcnow().isoformat(),
                user_id
            ))
        else:
            # INSERT
            cursor.execute("""
                INSERT INTO user_credentials
                (user_id, trabox_username, trabox_password_encrypted, webkit_api_key_encrypted, webkit_person_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                credentials.trabox_username,
                trabox_password_encrypted,
                webkit_api_key_encrypted,
                credentials.webkit_person_id,
                datetime.utcnow().isoformat()
            ))

        conn.commit()

        return {
            "status": "success",
            "message": "認証情報を保存しました"
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"保存に失敗しました: {str(e)}"
        )
    finally:
        conn.close()


@router.get("/api/settings/credentials")
async def get_credentials(current_user: dict = Depends(get_current_user)):
    """認証情報を取得（パスワードはマスク）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = current_user["id"]

    cursor.execute(
        """SELECT trabox_username, webkit_person_id FROM user_credentials WHERE user_id = ?""",
        (user_id,)
    )
    creds = cursor.fetchone()
    conn.close()

    if not creds:
        return {
            "trabox_username": None,
            "webkit_person_id": None
        }

    return {
        "trabox_username": creds[0],
        "webkit_person_id": creds[1]
    }
