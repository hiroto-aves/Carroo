"""暗号化・復号化ユーティリティ"""
from cryptography.fernet import Fernet
import os
from app.config import settings

# マスターキーを環境変数から取得、なければ生成
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"⚠️  ENCRYPTION_KEY が設定されていません。一時キーを使用します: {ENCRYPTION_KEY}")

cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def encrypt_password(password: str) -> str:
    """パスワードを暗号化"""
    return cipher.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """パスワードを復号化"""
    try:
        return cipher.decrypt(encrypted_password.encode()).decode()
    except Exception as e:
        raise ValueError(f"復号化に失敗しました: {e}")
