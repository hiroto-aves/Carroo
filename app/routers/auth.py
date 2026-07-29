import logging
import time
import threading

from fastapi import APIRouter, HTTPException, status, Response, Depends, Form, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models.schemas import UserCreate, User
from app.db.database import get_db_connection
from app.config import settings
from app.utils.security import hash_password, verify_password, create_access_token
from app.dependencies import get_current_user
from app.ui_shell import esc
from pydantic import BaseModel
from typing import Optional
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])

# ---- ログイン・レート制限（プロセス内メモリ。Cloud Run は max-instances=1 なので有効） ----
_LOGIN_MAX_FAILS = 8          # この回数まで失敗を許容
_LOGIN_WINDOW = 300           # 失敗カウントの観測窓（秒）
_LOGIN_LOCK = 900             # 上限到達後のロック時間（秒）
_login_attempts: dict = {}    # key -> {"fails":[timestamps], "locked_until":ts}
_login_lock = threading.Lock()


def _login_rate_limit_check(key: str) -> None:
    now = time.time()
    with _login_lock:
        rec = _login_attempts.get(key)
        if rec and rec.get("locked_until", 0) > now:
            wait = int(rec["locked_until"] - now)
            from app.utils.audit import audit
            audit("login_locked", key=key, wait_sec=wait)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"試行回数が多すぎます。約{wait//60 + 1}分後に再度お試しください。")


def _login_rate_limit_fail(key: str) -> None:
    now = time.time()
    with _login_lock:
        rec = _login_attempts.setdefault(key, {"fails": [], "locked_until": 0})
        rec["fails"] = [t for t in rec["fails"] if now - t < _LOGIN_WINDOW]
        rec["fails"].append(now)
        if len(rec["fails"]) >= _LOGIN_MAX_FAILS:
            rec["locked_until"] = now + _LOGIN_LOCK
            rec["fails"] = []


def _login_rate_limit_reset(key: str) -> None:
    with _login_lock:
        _login_attempts.pop(key, None)

@router.get("/login", response_class=HTMLResponse)
async def login_page():
    from app.ui_shell import brand_page
    inner = """
  <div class="panel">
    <h2>ログイン</h2>
    <div id="error-message" class="err"></div>
    <form id="login-form">
      <div class="field">
        <label class="fl">ユーザー名</label>
        <input type="text" name="username" placeholder="ユーザー名を入力" required>
      </div>
      <div class="field">
        <label class="fl">パスワード</label>
        <input type="password" name="password" autocomplete="current-password" placeholder="パスワードを入力" required>
      </div>
      <button type="submit" class="btn-primary">ログイン</button>
    </form>
    <p class="hint"><a href="/auth/forgot" style="color:var(--signal-ink)">パスワードをお忘れですか？</a></p>
    <p class="hint">アカウントが必要な場合は管理者にお問い合わせください</p>
  </div>
  <script>
    document.getElementById('login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorDiv = document.getElementById('error-message');
      try {
        const response = await fetch('/auth/login', { method: 'POST', body: new FormData(e.target) });
        const data = await response.json();
        if (response.ok) { window.location.href = data.redirect || '/dashboard/'; }
        else { errorDiv.textContent = data.detail || 'ログインに失敗しました'; errorDiv.classList.add('show'); window.__idle(e.target.__busyBtn); }
      } catch (error) {
        errorDiv.textContent = 'エラーが発生しました: ' + error.message; errorDiv.classList.add('show'); window.__idle(e.target.__busyBtn);
      }
    });
  </script>"""
    return brand_page(title="ログイン", inner=inner)


@router.get("/forgot", response_class=HTMLResponse)
async def forgot_page():
    from app.ui_shell import brand_page
    inner = """
  <div class="panel">
    <h2>パスワードの再設定</h2>
    <div id="error-message" class="err"></div>
    <div id="done" class="hint" style="display:none">✅ ご登録のメールアドレス宛に、再設定用のリンクをお送りしました（届かない場合は管理者にご確認ください）。</div>
    <form id="forgot-form">
      <div class="field">
        <label class="fl">登録済みのメールアドレス</label>
        <input type="email" name="email" placeholder="example@domain.com" required>
      </div>
      <button type="submit" class="btn-primary">再設定リンクを送る</button>
    </form>
    <p class="hint"><a href="/auth/login" style="color:var(--signal-ink)">← ログインへ戻る</a></p>
  </div>
  <script>
    document.getElementById('forgot-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorDiv = document.getElementById('error-message');
      const form = e.target;
      try {
        await fetch('/auth/forgot', { method: 'POST', body: new FormData(form) });
        form.style.display = 'none';
        document.getElementById('done').style.display = 'block';
      } catch (error) {
        errorDiv.textContent = 'エラーが発生しました: ' + error.message; errorDiv.classList.add('show');
        window.__idle(form.__busyBtn);
      }
    });
  </script>"""
    return brand_page(title="パスワードの再設定", inner=inner)


@router.post("/forgot")
async def forgot_request(email: str = Form(...)):
    """登録メールアドレス宛に再設定リンクを送信。アカウントの有無に関わらず同じ応答（列挙対策）。"""
    from app.db import store
    from app.utils.mailer import send_email
    import secrets
    users = [u for u in store.list_users() if (u.get("email") or "").lower() == email.strip().lower()]
    if users:
        user = users[0]
        token = secrets.token_urlsafe(32)
        store.create_password_reset(user["id"], token, ttl_minutes=30)
        import os
        base = (os.getenv("APP_BASE_URL", "") or "").rstrip("/")
        link = f"{base}/auth/reset?token={token}"
        body = (f"Carroo のパスワード再設定リクエストを受け付けました。\n\n"
                f"以下のリンクから新しいパスワードを設定してください（30分間有効）:\n{link}\n\n"
                f"心当たりがない場合は、このメールを無視してください。")
        try:
            send_email(user["email"], "【Carroo】パスワードの再設定", body)
        except Exception as e:
            logging.getLogger(__name__).error(f"パスワードリセットメール送信失敗: {e}")
    # アカウントの有無を外部から判別されないよう、常に同じ応答を返す
    return {"status": "ok"}


@router.get("/reset", response_class=HTMLResponse)
async def reset_page(token: str = ""):
    from app.ui_shell import brand_page
    inner = f"""
  <div class="panel">
    <h2>新しいパスワードを設定</h2>
    <div id="error-message" class="err"></div>
    <form id="reset-form">
      <input type="hidden" name="token" value="{esc(token)}">
      <div class="field">
        <label class="fl">新しいパスワード</label>
        <input type="password" name="password" autocomplete="new-password" placeholder="4文字以上" required>
      </div>
      <button type="submit" class="btn-primary">パスワードを更新</button>
    </form>
  </div>
  <script>
    document.getElementById('reset-form').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const errorDiv = document.getElementById('error-message');
      const data = Object.fromEntries(new FormData(e.target).entries());
      try {{
        const r = await fetch('/auth/reset', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(data)}});
        const j = await r.json();
        if (r.ok) {{ window.location.href = '/auth/login'; }}
        else {{ errorDiv.textContent = j.detail || '更新に失敗しました'; errorDiv.classList.add('show'); window.__idle(e.target.__busyBtn); }}
      }} catch (error) {{
        errorDiv.textContent = 'エラーが発生しました: ' + error.message; errorDiv.classList.add('show'); window.__idle(e.target.__busyBtn);
      }}
    }});
  </script>"""
    return brand_page(title="パスワードの再設定", inner=inner)


class PasswordResetApply(BaseModel):
    token: str
    password: str


@router.post("/reset")
async def reset_apply(data: PasswordResetApply):
    from app.db import store
    if len(data.password) < 4:
        raise HTTPException(400, "パスワードは4文字以上にしてください")
    user_id = store.consume_password_reset(data.token)
    if not user_id:
        raise HTTPException(400, "リンクが無効か期限切れです。もう一度お手続きください。")
    store.set_user_password(user_id, hash_password(data.password))
    from app.utils.audit import audit
    audit("password_reset_self", user_id=user_id)
    return {"status": "ok"}


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
        <link rel="stylesheet" href="/static/tailwind.css">
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
                                autocomplete="current-password"
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
async def login(request: Request, username: str = Form(...), password: str = Form(...),
                remember_me: str = Form(None), response: Response = None):
    if response is None:
        response = Response()

    # レート制限: 同一IP+ユーザー名の連続失敗をスロットル（総当り対策）
    client_ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                 or (request.client.host if request.client else "unknown"))
    _rl_key = f"{client_ip}|{username.lower()}"
    _login_rate_limit_check(_rl_key)

    from app.db import store
    user = store.get_user_by_username(username)

    from app.utils.audit import audit
    if not user or not verify_password(password, user["hashed_password"]):
        _login_rate_limit_fail(_rl_key)
        audit("login_failure", username=username, ip=client_ip)
        from app.errors import format_detail, user_message
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=format_detail(user_message("E-AUTH-401"), "E-AUTH-401"),
        )

    _login_rate_limit_reset(_rl_key)
    audit("login_success", username=username, user_id=user["id"], ip=client_ip)
    # 旧SHA-256 で保存されていたら、この機会に bcrypt へ透過的に再ハッシュ
    from app.utils.security import needs_rehash
    if needs_rehash(user["hashed_password"]):
        try:
            store.set_user_password(user["id"], hash_password(password))
        except Exception:
            logging.getLogger(__name__).warning("password rehash failed for user %s", user["id"])

    # 🔴 一生ログイン方針: 管理端末(Jamf配信)での利用のため常に永続ログイン。
    # スライディング更新と併せて、使い続ける限りログアウトされない。
    # セキュリティは「端末紛失＝アカウント削除」で担保（削除で即ログイン不能になる）。
    from app.utils.security import issue_access_token, set_auth_cookie, clear_auth_cookie
    access_token, max_age = issue_access_token(user["id"], remember=True)
    set_auth_cookie(response, access_token, max_age)

    # 運営者(super)は運営コンソールへ、それ以外はダッシュボードへ
    redirect = "/ops/" if user.get("is_super") else "/dashboard/"
    return {
        "status": "success",
        "redirect": redirect,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email"),
        },
        "message": "Login successful"
    }

@router.post("/logout")
async def logout(response: Response):
    from app.utils.security import clear_auth_cookie
    clear_auth_cookie(response)
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/logout")
async def logout_link():
    """ナビの「ログアウト」リンク（GET）用: Cookie を消してログイン画面へ"""
    from app.utils.security import clear_auth_cookie
    response = RedirectResponse(url="/auth/login", status_code=302)
    clear_auth_cookie(response)
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

    from app.db import store
    user = store.get_user_by_id(user_id)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    username, email, created_at = user["username"], user.get("email"), user.get("created_at")
    from app.ui_shell import render_page
    _u = {"id": user_id, "username": username, "email": email,
          "is_admin": user.get("is_admin"), "role": user.get("role"),
          "is_super": user.get("is_super"), "tenant_id": user.get("tenant_id"),
          "theme": user.get("theme") or "auto", "dashboard_mode": user.get("dashboard_mode") or "freight"}
    body = f"""
  <h1 class="pt">アカウント</h1>
  <p class="hl" style="margin:0 0 18px">ログインに使うユーザー名・メール・パスワードを変更できます。登録日: {esc(created_at) or '-'}</p>
  <div id="msg" class="hidden mb-4 p-3 rounded-lg" style="font-size:13px"></div>
  <div class="card" style="padding:22px;max-width:560px">
    <form id="acct">
      <div style="display:grid;gap:14px">
        <div><label class="fl">ユーザー名</label><input name="username" value="{esc(username)}" required></div>
        <div><label class="fl">メールアドレス</label><input type="email" name="email" value="{esc(email)}" required></div>
        <div><label class="fl">新しいパスワード（変更する場合のみ）</label>
          <input type="password" name="password" autocomplete="new-password" placeholder="空欄なら変更しません"></div>
      </div>
      <button type="submit" class="btn" style="margin-top:16px">保存する</button>
    </form>
  </div>
  <div style="margin-top:16px"><a class="btn ghost" href="/settings/">⚙ 初期設定（連絡先・認証情報）へ</a></div>
  <script>
  document.getElementById('acct').addEventListener('submit', async (e)=>{{
    e.preventDefault();
    const msg=document.getElementById('msg');
    const data=Object.fromEntries(new FormData(e.target).entries());
    try{{
      const r=await fetch('/auth/account',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});
      const j=await r.json();
      if(r.ok){{ msg.className='mb-4 p-3 rounded-lg bg-green-50 text-green-700'; msg.textContent='✅ 保存しました'; msg.classList.remove('hidden'); }}
      else {{ msg.className='mb-4 p-3 rounded-lg bg-red-50 text-red-700'; msg.textContent=(j.detail||'保存に失敗しました'); msg.classList.remove('hidden'); window.__idle(e.target.__busyBtn); }}
    }}catch(err){{ msg.className='mb-4 p-3 rounded-lg bg-red-50 text-red-700'; msg.textContent='エラー: '+err.message; msg.classList.remove('hidden'); window.__idle(e.target.__busyBtn); }}
  }});
  </script>"""
    return HTMLResponse(render_page(title="アカウント", active="settings", body=body,
                                    user=_u, crumb="Carroo"))


class AccountUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


@router.post("/account")
async def update_account(data: AccountUpdate,
                         current_user: dict = Depends(get_current_user)):
    """自分のログイン情報（ユーザー名・メール・パスワード）を更新。"""
    from app.db import store
    uid = current_user["id"]
    username = (data.username or "").strip()
    email = (data.email or "").strip()
    if not username or not email:
        raise HTTPException(400, "ユーザー名とメールアドレスは必須です")
    conflict = store.account_conflict(uid, username, email)
    if conflict:
        raise HTTPException(400, conflict)
    store.update_user_account(uid, username=username, email=email)
    if data.password:
        if len(data.password) < 4:
            raise HTTPException(400, "パスワードは4文字以上にしてください")
        store.set_user_password(uid, hash_password(data.password))
    from app.utils.audit import audit
    audit("account_update", user_id=uid, username=username)
    return {"status": "ok"}


@router.get("/api/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """現在のユーザー情報（JSON API）"""
    return current_user
