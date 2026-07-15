import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME = "OneLogi-Post"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./carroo.db")

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    # Automation
    TRABOX_URL = "https://www.torabox.com"
    TRABOX_HEADLESS = os.getenv("TRABOX_HEADLESS", "True").lower() == "true"

    # WebKIT API (XML-based)
    WEBKIT_API_URL = "https://www.wkit.jp/api/LoadInfo"
    WEBKIT_API_KEY = os.getenv("WEBKIT_API_KEY", "")  # 20-digit key
    WEBKIT_PERSON_ID = os.getenv("WEBKIT_PERSON_ID", "")  # 14-digit person ID

settings = Settings()
