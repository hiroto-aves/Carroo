"""Trabox 設定・定数"""

# ⚠️ IMPORTANT: 荷物登録は ONLY このページから行うこと！
# 他の似たようなフォームは全部違う形式のため、絶対に使ってはいけない！

TRABOX_LOGIN_URL = "https://www.trabox.com/login?return_to=/baggage/list/opened"
"""Trabox ログインページ"""

TRABOX_BAGGAGE_REGISTER_URL = "https://www.trabox.com/baggage/register"
"""🔴 【重要】荷物登録ページ - これが唯一の正しい登録ページ

   ⚠️  注意:
   - サイドバーから「+ 荷物登録」タブをクリック
   - または直接このURLにアクセス
   - 他の似たようなフォームは全部違う形式なので使用禁止！
"""

TRABOX_DASHBOARD_URL = "https://www.trabox.com/baggage/list/opened"
"""Trabox ダッシュボード（ログイン後）"""

# セレクター定義
TRABOX_SELECTORS = {
    "login_id": "input[name='loginid']",
    "login_password": "input[name='loginpwd']",
    "login_button": "span:has-text('ログイン')",
    "baggage_register_tab": "a:has-text('+ 荷物登録')",
    # 荷物登録フォームのフィールド
    "register_form": "form[class*='register'], form[class*='baggage']",
}
"""Trabox セレクター定義"""

# タイムアウト設定
TRABOX_TIMEOUTS = {
    "navigation": 30000,  # ページナビゲーション
    "selector": 10000,    # 要素待機
    "action": 5000,       # クリック・入力などのアクション
}
"""Trabox タイムアウト設定（ミリ秒）"""
