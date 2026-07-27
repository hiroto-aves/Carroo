"""マルチテナント対応レディ化（Stage 0）＋ フィーチャーフラグの一元判定。

現状は単一テナント運用。将来のマルチテナント化・機能のオプション販売に備え、
「テナントIDの取得」と「機能フラグの判定」をここ1箇所に集約する。

- current_tenant_id(): 今は固定値（DEFAULT_TENANT_ID）。将来は user/会社から導出。
- feature_enabled(name): 今は環境変数 FEATURE_<NAME>。将来はテナントの features を参照。
"""
import os

DEFAULT_TENANT_ID = "takeuchi"


def current_tenant_id(user: dict = None) -> str:
    """現在のテナントID。Stage 0 は固定（env DEFAULT_TENANT_ID）。
    将来: user["tenant_id"] や会社ドキュメントから導出する拡張点。"""
    if user and user.get("tenant_id"):
        return user["tenant_id"]
    return os.getenv("DEFAULT_TENANT_ID", DEFAULT_TENANT_ID)


def get_current_tenant(user: dict = None) -> dict:
    """現在のテナントdocを返す（無ければ空dict）。features/plan の参照元。"""
    try:
        from app.db import store
        return store.get_tenant(current_tenant_id(user)) or {}
    except Exception:
        return {}


def _plan_features(plan: str) -> dict:
    """プラン → 解放される機能。Pro のみ定期/複数日程/再登録を解放。"""
    pro = plan == "pro"
    return {"recurring": pro, "multidate": pro, "reregister": pro}


def feature_enabled(name: str, user: dict = None) -> bool:
    """機能フラグ判定。優先順:
      1. user.features[name]（個別上書き・テスト用）
      2. user.tenant_features[name]（ログイン時にテナントから注入。Firestore追加読みを避ける）
      3. テナックの plan 由来（tenant.plan → _plan_features）
      4. 環境変数 FEATURE_<NAME>（従来フォールバック）
    テナントに plan/features がまだ無い現行は 4 に落ちる＝挙動不変。"""
    if user and isinstance(user.get("features"), dict) and name in user["features"]:
        return bool(user["features"][name])
    if user and isinstance(user.get("tenant_features"), dict) and name in user["tenant_features"]:
        return bool(user["tenant_features"][name])
    if user and user.get("tenant_plan"):
        pf = _plan_features(user["tenant_plan"])
        if name in pf:
            # 明示的にプランで管理する機能はプラン判定を優先（課金稼働後）
            if _billing_active():
                return bool(pf[name])
    val = os.getenv(f"FEATURE_{name.upper()}", "off").strip().lower()
    return val in ("on", "true", "1", "yes")


def _billing_active() -> bool:
    """課金モードが有効か（env BILLING_ENABLED）。無効時はプラン判定を使わず env フォールバック
    ＝現行の単一テナント運用を壊さない。Stripe 連携完了後に on にする。"""
    return os.getenv("BILLING_ENABLED", "off").strip().lower() in ("on", "true", "1", "yes")
