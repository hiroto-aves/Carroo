"""ユーザー設定ルーター"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from app.utils.encryption import encrypt_password, decrypt_password
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(tags=["settings"])


class CredentialsInput(BaseModel):
    trabox_username: str = None
    trabox_password: str = None
    webkit_person_id: str = None
    contact_name: str = None
    contact_phone: str = None
    contact_email: str = None


def get_settings_html(
    username: str,
    trabox_username: str,
    webkit_person_id: str,
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
) -> str:
    """設定ページHTMLを生成"""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carroo - 初期設定</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50">
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
        <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">初期設定</h1>
            <p class="text-gray-600 mt-2">Trabox と WebKit の認証情報を登録してください</p>
        </div>

        <div class="bg-white rounded-lg shadow-md p-8">
            <form id="settings-form" class="space-y-8">
                <div id="error-message" class="hidden p-4 bg-red-50 border border-red-200 rounded-lg text-red-700"></div>
                <div id="success-message" class="hidden p-4 bg-green-50 border border-green-200 rounded-lg text-green-700"></div>

                <div class="border-b pb-8">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">🚚 Trabox 認証情報</h2>
                    <div class="space-y-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">ユーザー名（メールアドレス）</label>
                            <input type="email" name="trabox_username" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="example@domain.com" value="{trabox_username}">
                            <p class="text-xs text-gray-500 mt-1">Trabox のログインメールアドレス</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">パスワード</label>
                            <input type="password" name="trabox_password" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="パスワードを入力">
                            <p class="text-xs text-gray-500 mt-1">※ サーバーに暗号化して保存されます</p>
                        </div>
                    </div>
                </div>

                <div class="border-b pb-8">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">🌐 WebKit API 設定</h2>
                    <div class="space-y-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">担当者 ID（14桁）</label>
                            <input type="text" name="webkit_person_id" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition font-mono" placeholder="14桁の担当者ID" value="{webkit_person_id}" maxlength="14">
                            <p class="text-xs text-gray-500 mt-1">例: 12345678901234</p>
                        </div>
                        <div class="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                            <p class="text-sm text-blue-800">
                                <strong>📌 API キー:</strong> WebKit API キーは管理者により環境変数で一括管理されています。
                            </p>
                        </div>
                    </div>
                </div>

                <div class="border-b pb-8">
                    <h2 class="text-xl font-semibold text-gray-900 mb-6">📞 案件登録の連絡先情報（初期値）</h2>
                    <p class="text-sm text-gray-500 mb-4">ここに登録した内容が、案件登録フォームの連絡先に自動で入力されます</p>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">担当者名</label>
                            <input type="text" name="contact_name" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="山田太郎" value="{contact_name}">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">電話番号</label>
                            <input type="tel" name="contact_phone" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="09012345678" value="{contact_phone}">
                        </div>
                        <div class="md:col-span-2">
                            <label class="block text-sm font-medium text-gray-700 mb-2">メールアドレス<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                            <input type="email" name="contact_email" required class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="example@domain.com" value="{contact_email}">
                            <p class="text-xs text-gray-500 mt-1">投稿の成否通知がこのアドレスに届きます。未登録の場合は案件登録できません。</p>
                        </div>
                    </div>
                </div>

                <div class="flex gap-4">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-6 rounded-lg transition duration-200">保存する</button>
                    <a href="/dashboard/" class="bg-gray-300 hover:bg-gray-400 text-gray-900 font-semibold py-2.5 px-6 rounded-lg transition duration-200">キャンセル</a>
                </div>
            </form>
        </div>

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
        document.getElementById('settings-form').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const errorDiv = document.getElementById('error-message');
            const successDiv = document.getElementById('success-message');
            errorDiv.classList.add('hidden');
            successDiv.classList.add('hidden');

            const formData = new FormData(e.target);
            const data = {{
                trabox_username: formData.get('trabox_username') || null,
                trabox_password: formData.get('trabox_password') || null,
                webkit_person_id: formData.get('webkit_person_id') || null,
                contact_name: formData.get('contact_name') || null,
                contact_phone: formData.get('contact_phone') || null,
                contact_email: formData.get('contact_email') || null,
            }};

            try {{
                const response = await fetch('/api/settings/credentials/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});

                const result = await response.json();
                if (response.ok) {{
                    successDiv.textContent = '✅ 設定を保存しました！';
                    successDiv.classList.remove('hidden');
                    setTimeout(() => {{
                        window.location.href = '/dashboard/';
                    }}, 2000);
                }} else {{
                    errorDiv.textContent = result.detail || '保存に失敗しました';
                    errorDiv.classList.remove('hidden');
                }}
            }} catch (error) {{
                errorDiv.textContent = 'エラーが発生しました: ' + error.message;
                errorDiv.classList.remove('hidden');
            }}
        }});
    </script>
</body>
</html>"""


@router.get("/settings/", response_class=HTMLResponse)
async def settings_page(current_user: dict = Depends(get_current_user)):
    """設定ページ"""
    user_id = current_user["id"]
    username = current_user["username"]

    from app.db import store
    creds = store.get_credentials(user_id)

    return get_settings_html(
        username,
        creds.get("trabox_username", "") or "",
        creds.get("webkit_person_id", "") or "",
        creds.get("contact_name", "") or "",
        creds.get("contact_phone", "") or "",
        creds.get("contact_email", "") or "",
    )


@router.post("/api/settings/credentials/")
async def save_credentials(
    credentials: CredentialsInput,
    current_user: dict = Depends(get_current_user)
):
    """認証情報を保存"""
    from app.db import store
    user_id = current_user["id"]

    # メールアドレスは必須（投稿成否の通知先。未登録だと案件登録できない）
    if not credentials.contact_email:
        existing = store.get_credentials(user_id)
        if not existing.get("contact_email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="メールアドレスは必須です（投稿成否の通知先になります）",
            )

    trabox_password_encrypted = (
        encrypt_password(credentials.trabox_password)
        if credentials.trabox_password
        else None
    )
    # None のフィールドは upsert_credentials 側で無視され既存値を維持
    store.upsert_credentials(user_id, {
        "trabox_username": credentials.trabox_username,
        "trabox_password_encrypted": trabox_password_encrypted,
        "webkit_person_id": credentials.webkit_person_id,
        "contact_name": credentials.contact_name,
        "contact_phone": credentials.contact_phone,
        "contact_email": credentials.contact_email,
        "updated_at": datetime.utcnow().isoformat(),
    })
    return {"status": "success", "message": "認証情報を保存しました"}


@router.get("/api/settings/credentials/")
async def get_credentials(current_user: dict = Depends(get_current_user)):
    """認証情報を取得（パスワードはマスク）"""
    from app.db import store
    user_id = current_user["id"]
    _c = store.get_credentials(user_id)
    creds = (_c.get("trabox_username"), _c.get("webkit_person_id"))

    if not creds:
        return {
            "trabox_username": None,
            "webkit_person_id": None
        }

    return {
        "trabox_username": creds[0],
        "webkit_person_id": creds[1]
    }
