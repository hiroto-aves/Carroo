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

    WEBKIT_API_URL = "https://api.webkit.jp"
    WEBKIT_API_KEY = os.getenv("WEBKIT_API_KEY", "")

settings = Settings()
