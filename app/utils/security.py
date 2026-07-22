from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.config import settings
import hashlib

def hash_password(password: str) -> str:
    """パスワードをハッシュ化"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワード検証"""
    return hash_password(plain_password) == hashed_password

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """JWT アクセストークン生成"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm="HS256"
    )

    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """JWT トークンをデコード"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def _token_lifetime(remember: bool) -> timedelta:
    """ログイン保持フラグに応じた有効期限を返す"""
    if remember:
        return timedelta(days=settings.REMEMBER_ME_DAYS)
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def issue_access_token(user_id: int, remember: bool) -> tuple:
    """user_id と remember から (token, max_age秒) を生成

    token 内に remember フラグを埋め込み、スライディング更新時に同じ寿命を再適用できる。
    """
    lifetime = _token_lifetime(remember)
    token = create_access_token(
        {"user_id": user_id, "remember": remember}, expires_delta=lifetime
    )
    return token, int(lifetime.total_seconds())


def set_auth_cookie(response, token: str, max_age: int) -> None:
    """認証Cookieをセット（httponly / samesite=lax / secure は設定に従う）

    secure は本番HTTPSで True（COOKIE_SECURE=True）。ローカルHTTPでは False。
    """
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    """認証Cookieを削除（属性を set 時と揃える）"""
    response.delete_cookie(
        key="access_token", path="/", samesite="lax", secure=settings.COOKIE_SECURE
    )
