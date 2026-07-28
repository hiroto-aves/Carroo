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

    # マルチテナント（Stage 1）: ロール／テナント情報を付与。
    # role: owner(会社管理者) | member(一般)。is_super: 運営者(全テナント横断)。
    role = user.get("role") or ("owner" if user.get("is_admin") else "member")
    is_super = bool(user.get("is_super"))
    tenant_id = user.get("tenant_id")
    tenant_features, tenant_plan = {}, None
    try:
        from app.tenancy import current_tenant_id
        tenant = store.get_tenant(current_tenant_id({"tenant_id": tenant_id})) or {}
        tenant_features = tenant.get("features") or {}
        tenant_plan = tenant.get("plan")
    except Exception:
        pass

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
        # 後方互換: is_admin は「会社管理者(owner) か 運営者(super)」を表す
        "is_admin": bool(user.get("is_admin")) or role == "owner" or is_super,
        "role": role,
        "is_super": is_super,
        "tenant_id": tenant_id,
        # ユーザー個別の機能付与（運営者が /ops で設定）。feature_enabled が最優先で参照。
        "features": user.get("features") or {},
        "tenant_features": tenant_features,
        "tenant_plan": tenant_plan,
        # 表示設定（ユーザー別）: theme=auto|light|dark, dashboard_mode=freight|truck
        "theme": user.get("theme") or "auto",
        "dashboard_mode": user.get("dashboard_mode") or "freight",
    }
