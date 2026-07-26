"""監査ログ（セキュリティ・重要操作の追跡）。

Cloud Run の stdout はそのまま Cloud Logging に集約される。ここでは各イベントを
`[AUDIT]` プレフィックス＋JSON で1行出力し、Cloud Logging 側で
`textPayload:"[AUDIT]"` や log-based metric によりフィルタ・集計・アラートできる。

用途例:
- login_failure / login_locked … ログイン失敗・ロックの追跡（総当り検知）
- case/truck の register・update・delete … 誰がいつ何を操作したか
"""
import json
import logging

logger = logging.getLogger("audit")


def audit(event: str, **fields) -> None:
    """監査イベントを1行のJSONで出力する。fields は任意の付帯情報。"""
    payload = {"event": event}
    # None は落とし、値は文字列化しすぎない（数値・boolはそのまま）
    for k, v in fields.items():
        if v is not None:
            payload[k] = v
    try:
        logger.info("[AUDIT] %s", json.dumps(payload, ensure_ascii=False))
    except Exception:
        # ログ出力の失敗は業務処理に影響させない
        logger.info("[AUDIT] %s", {"event": event})
