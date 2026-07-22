import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME = "Carroo"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./carroo.db")

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
    # 非「ログイン保持」時の有効期限（分）。アクティブなら都度スライド更新される
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8時間
    # 「ログイン状態を保持する」選択時の有効期限（日）
    REMEMBER_ME_DAYS = int(os.getenv("REMEMBER_ME_DAYS", "30"))
    # Cookie を HTTPS 通信でのみ送る（本番=True / ローカルHTTP=False）
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "False").lower() == "true"

    # Automation - Trabox
    TRABOX_URL = "https://www.trabox.com"
    TRABOX_LOGIN_URL = "https://www.trabox.com/login?return_to=/baggage/list/opened"
    TRABOX_HEADLESS = os.getenv("TRABOX_HEADLESS", "True").lower() == "true"

    # Trabox Test Account (セキュアな環境変数から読み込み)
    TRABOX_TEST_USERNAME = os.getenv("TRABOX_TEST_USERNAME", "")
    TRABOX_TEST_PASSWORD = os.getenv("TRABOX_TEST_PASSWORD", "")

    # Trabox 本番アカウント (オプション)
    TRABOX_PROD_USERNAME = os.getenv("TRABOX_PROD_USERNAME", "")
    TRABOX_PROD_PASSWORD = os.getenv("TRABOX_PROD_PASSWORD", "")

    # Automation - WebKIT (Browser automation + API)
    WEBKIT_URL = "https://www.wkit.jp"

    # ブラウザ自動化用のログイン情報
    WEBKIT_LOGIN_ID = os.getenv("WEBKIT_LOGIN_ID", "")
    WEBKIT_LOGIN_PASSWORD = os.getenv("WEBKIT_LOGIN_PASSWORD", "")

    # API方式の認証情報
    WEBKIT_API_URL = "https://www.wkit.jp/api/LoadInfo"
    WEBKIT_API_KEY = os.getenv("WEBKIT_API_KEY", "")  # 20-digit key
    WEBKIT_PERSON_ID = os.getenv("WEBKIT_PERSON_ID", "")  # 14-digit person ID

settings = Settings()
