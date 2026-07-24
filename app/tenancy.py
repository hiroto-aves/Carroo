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


def feature_enabled(name: str, user: dict = None) -> bool:
    """機能フラグ判定。Stage 0 は環境変数 FEATURE_<NAME>（on/true/1/yes で有効）。
    将来: テナントの features.<name> を優先し、無ければ env にフォールバック。"""
    # 将来のテナント別フラグ拡張点（user/会社の features を先に見る）
    if user and isinstance(user.get("features"), dict) and name in user["features"]:
        return bool(user["features"][name])
    val = os.getenv(f"FEATURE_{name.upper()}", "off").strip().lower()
    return val in ("on", "true", "1", "yes")
