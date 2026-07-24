"""全ページ共通のナビゲーションバー。

後から足した機能（空車・繰り返し）への導線が各ページでズレないよう、
ナビを1箇所に集約する。繰り返しは FEATURE_RECURRING 有効時のみ表示。
"""
from app.tenancy import feature_enabled


def main_nav(username: str = "", is_admin: bool = False) -> str:
    recurring = ('<a href="/schedules/" class="text-gray-600 hover:text-blue-600 transition">🔁 繰り返し</a>'
                 if feature_enabled("recurring") else "")
    admin = ('<a href="/admin/users" class="text-gray-600 hover:text-blue-600 transition">👥 ユーザー管理</a>'
             if is_admin else "")
    user = f'<span class="text-sm text-gray-500 hidden lg:inline">{username}</span>' if username else ""
    return f"""<nav class="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><div class="flex justify-between h-16 items-center gap-2">
    <a href="/dashboard/" class="text-2xl font-bold text-blue-600 whitespace-nowrap">📦 Carroo</a>
    <div class="flex items-center gap-3 text-sm flex-wrap justify-end">
      <a href="/dashboard/" class="text-gray-600 hover:text-blue-600 transition">ダッシュボード</a>
      <a href="/cases/register" class="text-gray-600 hover:text-blue-600 transition">🚚 荷物登録</a>
      <a href="/trucks/register" class="text-gray-600 hover:text-blue-600 transition">🅿️ 空車登録</a>
      <a href="/trucks/" class="text-gray-600 hover:text-blue-600 transition">空車一覧</a>
      {recurring}
      {admin}
      <a href="/settings/" class="text-gray-600 hover:text-blue-600 transition">⚙️ 設定</a>
      {user}
      <a href="/auth/logout" class="text-gray-600 hover:text-red-600 transition">ログアウト</a>
    </div>
  </div></div></nav>"""
