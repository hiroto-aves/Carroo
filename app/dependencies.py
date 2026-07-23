from fastapi import Depends, HTTPException, status, Cookie
from typing import Optional
from app.utils.security import decode_access_token
from app.db.database import get_db_connection

async def get_current_user(access_token: Optional[str] = Cookie(None)):
    """現在のユーザー情報を取得"""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(access_token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = token_data.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    from app.db import store
    user = store.get_user_by_id(user_id)

    if user is None:
        # ユーザーが削除された場合（端末紛失時の無効化等）は即認証エラー
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        "is_admin": bool(user.get("is_admin")),
    }
