from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.config import settings
import hashlib
import bcrypt


def hash_password(password: str) -> str:
    """パスワードをハッシュ化（bcrypt。ソルト付き・低速で総当り耐性）。

    bcrypt は 72 バイト超を無視するため、先に SHA-256 で固定長化してから
    bcrypt にかける（長いパスワードでも全体が反映される標準的な前処理）。
    """
    pre = hashlib.sha256(password.encode("utf-8")).digest()
    return bcrypt.hashpw(pre, bcrypt.gensalt()).decode("ascii")


def _is_bcrypt(h: str) -> bool:
    return isinstance(h, str) and h.startswith(("$2a$", "$2b$", "$2y$"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワード検証。bcrypt と 旧SHA-256(移行用) の両方を受け付ける。"""
    if not hashed_password:
        return False
    if _is_bcrypt(hashed_password):
        pre = hashlib.sha256(plain_password.encode("utf-8")).digest()
        try:
            return bcrypt.checkpw(pre, hashed_password.encode("ascii"))
        except ValueError:
            return False
    # 旧形式（無ソルト SHA-256 hexdigest）: 移行期間のみ検証を許可
    legacy = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return legacy == hashed_password


def needs_rehash(hashed_password: str) -> bool:
    """旧SHA-256で保存されている＝ログイン成功時に bcrypt へ再ハッシュすべきか。"""
    return not _is_bcrypt(hashed_password or "")

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
