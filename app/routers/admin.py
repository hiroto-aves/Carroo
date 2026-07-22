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


def _nav(username: str) -> str:
    return f"""
    <nav class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-4xl mx-auto px-4 py-3.5 flex items-center justify-between">
        <a href="/dashboard/" class="text-2xl font-bold text-blue-600 hover:opacity-80">📦 Carroo</a>
        <div class="flex gap-4 text-sm text-gray-600 items-center">
          <span class="text-gray-400">{username}（管理者）</span>
          <a href="/dashboard/" class="hover:text-blue-600">ダッシュボード</a>
          <a href="/auth/logout" class="hover:text-red-600">ログアウト</a>
        </div>
      </div>
    </nav>"""


@router.get("/users", response_class=HTMLResponse)
async def users_page(current_user: dict = Depends(get_current_user)):
    """ユーザー管理画面（一覧＋新規発行フォーム）。管理者のみ。"""
    _require_admin(current_user)
    conn = get_db_connection()
    users = conn.execute(
        """SELECT u.id, u.username, u.email, COALESCE(u.is_admin,0), u.created_at,
                  (SELECT COUNT(*) FROM cases c WHERE c.user_id = u.id)
           FROM users u ORDER BY u.id"""
    ).fetchall()
    conn.close()

    rows = ""
    for uid, uname, email, is_admin, created, ncases in users:
        badge = ('<span class="text-xs font-bold px-2 py-0.5 rounded bg-blue-50 '
                 'text-blue-700 border border-blue-200">管理者</span>') if is_admin else \
                '<span class="text-xs text-gray-400">一般</span>'
        rows += f"""
        <tr class="border-b border-gray-100 hover:bg-gray-50">
          <td class="px-4 py-3 text-sm font-mono text-gray-500">{uid}</td>
          <td class="px-4 py-3 text-sm font-semibold text-gray-900">{uname} {badge}</td>
          <td class="px-4 py-3 text-sm text-gray-600">{email}</td>
          <td class="px-4 py-3 text-sm text-gray-600 text-right tabular-nums">{ncases} 件</td>
          <td class="px-4 py-3 text-sm text-gray-400">{created or ''}</td>
        </tr>"""

    I = ('w-full px-3 py-2 border border-gray-300 rounded-lg '
         'focus:ring-2 focus:ring-blue-500')
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carroo - ユーザー管理</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50">{_nav(current_user['username'])}
<div class="max-w-4xl mx-auto px-4 py-8">
  <p class="text-sm text-gray-500 mb-3"><a href="/dashboard/" class="text-blue-600">ダッシュボード</a> › ユーザー管理</p>
  <h1 class="text-2xl font-bold mb-6">ユーザー管理</h1>

  <div class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-8">
    <table class="w-full">
      <thead class="bg-gray-50 border-b border-gray-200">
        <tr>
          <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">ID</th>
          <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">ユーザー名</th>
          <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">メール</th>
          <th class="px-4 py-2.5 text-right text-xs font-semibold text-gray-600">登録案件</th>
          <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-600">作成日</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <h2 class="text-lg font-bold mb-3">新しいユーザーを発行</h2>
  <form method="post" action="/admin/users" class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div><label class="block text-sm font-medium mb-1">ユーザー名 <span class="text-red-500">*</span></label>
        <input name="username" class="{I}" required placeholder="例: 山田太郎"></div>
      <div><label class="block text-sm font-medium mb-1">メールアドレス <span class="text-red-500">*</span></label>
        <input type="email" name="email" class="{I}" required placeholder="user@example.com"></div>
      <div><label class="block text-sm font-medium mb-1">初期パスワード <span class="text-red-500">*</span></label>
        <input name="password" class="{I}" required placeholder="8文字以上を推奨"></div>
      <div class="flex items-end"><label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="is_admin" value="yes" class="w-4 h-4"> このユーザーも管理者にする</label></div>
    </div>
    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg">ユーザーを発行</button>
    <p class="text-xs text-gray-500">発行後、そのユーザーはメール（ユーザー名）と初期パスワードでログインし、初期設定画面で認証情報・連絡先を登録します。</p>
  </form>
</div></body></html>""")


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
    conn = get_db_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?", (username, email)
        ).fetchone()
        if exists:
            raise HTTPException(
                status_code=400,
                detail="同じユーザー名またはメールが既に存在します",
            )
        conn.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) "
            "VALUES (?, ?, ?, ?)",
            (username, email, hash_password(password), 1 if is_admin == "yes" else 0),
        )
        conn.commit()
        logger.info(f"[Admin] ユーザー発行: {username} (by {current_user['username']})")
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return RedirectResponse(url="/admin/users", status_code=302)
