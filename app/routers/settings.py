"""ユーザー設定ルーター"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from app.dependencies import get_current_user
from app.db.database import get_db_connection
from app.utils.encryption import encrypt_password, decrypt_password
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(tags=["settings"])


class CredentialsInput(BaseModel):
    # Optional にしないと、空欄フィールドが JSON の null で送られた際に
    # Pydantic v2 が「str なのに null」で 422 を返してしまう
    trabox_username: Optional[str] = None
    trabox_password: Optional[str] = None
    webkit_person_id: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None


def get_settings_html(
    username: str,
    trabox_username: str,
    webkit_person_id: str,
    contact_name: str = "",
    contact_phone: str = "",
    contact_email: str = "",
    theme: str = "auto",
    dashboard_mode: str = "freight",
    user: dict = None,
    has_trabox_password: bool = False,
) -> str:
    """設定ページHTMLを生成"""
    from app.ui_shell import shell_open, SHELL_CLOSE, esc
    # パスワードは復号表示しない。登録済みなら「登録済み」と分かる表示にし、
    # 空欄のまま保存すれば既存パスワードを維持する旨を明示する。
    if has_trabox_password:
        pw_badge = ('<span class="ml-2 px-1.5 py-0.5 text-xs font-semibold text-green-700 '
                    'bg-green-50 border border-green-200 rounded">登録済み</span>')
        pw_placeholder = "●●●●●●●●（変更する場合のみ入力）"
        pw_note = "※ 登録済み。変更しないなら空欄のままでOK（既存のパスワードを維持します）"
    else:
        pw_badge = ""
        pw_placeholder = "パスワードを入力"
        pw_note = "※ サーバーに暗号化して保存されます"

    def _sel(cur, val):
        return " selected" if cur == val else ""

    theme_section = f"""
        <div class="bg-white rounded-lg shadow-md p-8 mb-6" style="background:var(--surface);border:1px solid var(--line)">
            <h2 class="text-xl font-semibold mb-1" style="color:var(--ink)">🎨 表示設定</h2>
            <p class="text-sm mb-6" style="color:var(--muted)">この端末ではなく、あなたのアカウントに保存されます。</p>
            <div id="prefs-msg" class="hidden mb-4 p-3 rounded-lg"></div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                <div>
                    <label class="block text-sm font-medium mb-2" style="color:var(--ink-2)">テーマ（ダーク / ライト）</label>
                    <select id="pref-theme" style="width:100%">
                        <option value="auto"{_sel(theme,'auto')}>自動（OSの設定に従う）</option>
                        <option value="light"{_sel(theme,'light')}>ライト（明るい）</option>
                        <option value="dark"{_sel(theme,'dark')}>ダーク（暗い）</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium mb-2" style="color:var(--ink-2)">トップページに表示する内容</label>
                    <select id="pref-dash" style="width:100%">
                        <option value="freight"{_sel(dashboard_mode,'freight')}>荷物の評価（投稿数・成約・進行中の経路）</option>
                        <option value="truck"{_sel(dashboard_mode,'truck')}>空車ミックス（空車一覧＋空車定期登録一覧）</option>
                    </select>
                </div>
            </div>
            <button type="button" id="save-prefs" class="mt-6 btn">表示設定を保存</button>
        </div>
    """

    return shell_open(title="初期設定", active="settings",
                      user=user or {"username": username}) + f"""
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="mb-8">
            <h1 class="text-3xl font-bold" style="color:var(--ink)">初期設定</h1>
        </div>
        {theme_section}
    </div>
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-8">
        <div class="mb-6">
            <h2 class="text-xl font-semibold" style="color:var(--ink)">🔐 認証情報・連絡先</h2>
            <p class="mt-1 text-sm" style="color:var(--muted)">Trabox と WebKit の認証情報を登録してください</p>
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
                            <label class="block text-sm font-medium text-gray-700 mb-2">パスワード{pw_badge}</label>
                            <input type="password" name="trabox_password" autocomplete="current-password" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="{pw_placeholder}">
                            <p class="text-xs text-gray-500 mt-1">{pw_note}</p>
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
                            <input type="text" name="contact_name" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="山田太郎" value="{esc(contact_name)}">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">電話番号</label>
                            <input type="tel" name="contact_phone" class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="09012345678" value="{esc(contact_phone)}">
                        </div>
                        <div class="md:col-span-2">
                            <label class="block text-sm font-medium text-gray-700 mb-2">メールアドレス<span class="ml-1 px-1.5 py-0.5 text-xs font-semibold text-red-600 bg-red-50 rounded">必須</span></label>
                            <input type="email" name="contact_email" required class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition" placeholder="example@domain.com" value="{esc(contact_email)}">
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
                    let d = result.detail;
                    if (Array.isArray(d)) d = d.map(x => x.msg || JSON.stringify(x)).join(' / ');
                    else if (d && typeof d === 'object') d = JSON.stringify(d);
                    errorDiv.textContent = d || '保存に失敗しました';
                    errorDiv.classList.remove('hidden');
                    window.__idle(e.target.__busyBtn);
                }}
            }} catch (error) {{
                errorDiv.textContent = 'エラーが発生しました: ' + error.message;
                errorDiv.classList.remove('hidden');
                window.__idle(e.target.__busyBtn);
            }}
        }});

        // 表示設定（テーマ・トップページ内容）の保存
        document.getElementById('save-prefs').addEventListener('click', async () => {{
            const msg = document.getElementById('prefs-msg');
            const data = {{
                theme: document.getElementById('pref-theme').value,
                dashboard_mode: document.getElementById('pref-dash').value,
            }};
            try {{
                const r = await fetch('/api/settings/prefs/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                if (r.ok) {{
                    // テーマ即時反映のためリロード
                    location.reload();
                }} else {{
                    const j = await r.json();
                    msg.textContent = j.detail || '保存に失敗しました';
                    msg.className = 'mb-4 p-3 rounded-lg bg-red-50 text-red-700';
                    msg.classList.remove('hidden');
                }}
            }} catch (err) {{
                msg.textContent = 'エラー: ' + err.message;
                msg.className = 'mb-4 p-3 rounded-lg bg-red-50 text-red-700';
                msg.classList.remove('hidden');
            }}
        }});
    </script>
""" + SHELL_CLOSE


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
        theme=current_user.get("theme", "auto"),
        dashboard_mode=current_user.get("dashboard_mode", "freight"),
        user=current_user,
        has_trabox_password=bool(creds.get("trabox_password_encrypted")),
    )


class PrefsInput(BaseModel):
    theme: str = None
    dashboard_mode: str = None


@router.post("/api/settings/prefs/")
async def save_prefs(prefs: PrefsInput,
                     current_user: dict = Depends(get_current_user)):
    """表示設定（テーマ・トップページ内容）をユーザードキュメントに保存。"""
    from app.db import store
    theme = prefs.theme if prefs.theme in ("auto", "light", "dark") else None
    mode = prefs.dashboard_mode if prefs.dashboard_mode in ("freight", "truck") else None
    store.set_user_prefs(current_user["id"], {"theme": theme, "dashboard_mode": mode})
    return {"status": "success"}


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
