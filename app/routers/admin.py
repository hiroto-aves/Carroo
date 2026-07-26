"""管理者用ルーター

管理者のみアクセス可能:
- ユーザー管理（一覧・新規発行）
- （案件の横断検索はダッシュボードの案件一覧で is_admin により全件表示）
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.database import get_db_connection
from app.dependencies import get_current_user
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user: dict):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この操作には管理者権限が必要です",
        )


@router.get("/users", response_class=HTMLResponse)
async def users_page(current_user: dict = Depends(get_current_user)):
    """ユーザー管理画面（一覧＋新規発行フォーム）。管理者のみ。左レール・シェル。"""
    _require_admin(current_user)
    from app.db import store
    from app.ui_shell import render_page
    users = [
        (u["id"], u["username"], u.get("email"), u.get("is_admin"),
         u.get("created_at"), store.count_user_cases(u["id"]))
        for u in store.list_users()
    ]

    rows = ""
    for uid, uname, email, is_admin, created, ncases in users:
        badge = ('<span class="chip met" style="margin-left:6px">管理者</span>'
                 if is_admin else '<span class="chip off" style="margin-left:6px">一般</span>')
        rows += f"""
        <tr>
          <td class="mono" style="color:var(--faint)">{uid}</td>
          <td style="font-weight:600">{uname}{badge}</td>
          <td style="color:var(--muted)">{email or ''}</td>
          <td class="num" style="text-align:right">{ncases} 件</td>
          <td style="color:var(--faint)">{created or ''}</td>
        </tr>"""

    body = f"""
  <h1 class="pt">ユーザー管理</h1>
  <p class="hl" style="margin:0 0 18px">社内ユーザーの一覧と、新規ユーザーの発行。</p>

  <div class="card" style="overflow:hidden;margin-bottom:22px">
    <table>
      <thead><tr>
        <th>ID</th><th>ユーザー名</th><th>メール</th>
        <th style="text-align:right">登録案件</th><th>作成日</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <style>.uform input{{padding:12px 15px}}.uform input::placeholder{{color:var(--faint)}}</style>
  <div class="card" style="padding:22px;max-width:680px">
    <h2 style="font-size:16px;margin:0 0 16px">新しいユーザーを発行</h2>
    <form class="uform" method="post" action="/admin/users">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div><label class="fl">ユーザー名 *</label><input name="username" required placeholder="例: 山田太郎"></div>
        <div><label class="fl">メールアドレス *</label><input type="email" name="email" required placeholder="user@example.com"></div>
        <div><label class="fl">初期パスワード *</label><input name="password" required placeholder="4文字以上"></div>
        <div style="display:flex;align-items:flex-end"><label style="display:flex;gap:8px;align-items:center;font-size:13px;color:var(--ink)">
          <input type="checkbox" name="is_admin" value="yes" style="width:auto"> このユーザーも管理者にする</label></div>
      </div>
      <button type="submit" class="btn" style="margin-top:16px">ユーザーを発行</button>
      <p class="hl" style="margin:12px 0 0;font-size:12px">発行後、そのユーザーはメール（ユーザー名）と初期パスワードでログインし、初期設定画面で認証情報・連絡先を登録します。</p>
    </form>
  </div>"""

    return HTMLResponse(render_page(
        title="ユーザー管理", active="users", body=body, user=current_user,
        crumb="Carroo · 管理"))


@router.post("/users")
async def create_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """新規ユーザー発行（管理者のみ）"""
    _require_admin(current_user)
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="パスワードは4文字以上にしてください")
    from app.db import store
    if store.user_exists(username, email):
        raise HTTPException(
            status_code=400,
            detail="同じユーザー名またはメールが既に存在します",
        )
    store.create_user(username, email, hash_password(password),
                      is_admin=(is_admin == "yes"))
    logger.info(f"[Admin] ユーザー発行: {username} (by {current_user['username']})")
    return RedirectResponse(url="/admin/users", status_code=302)
