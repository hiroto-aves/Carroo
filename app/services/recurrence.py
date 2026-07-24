"""繰り返しルールの日付展開エンジン（Googleカレンダー風）。

対応: DAILY / WEEKLY / BIWEEKLY / MONTHLY
- byday: 曜日インデックス [0=月 .. 6=日]（WEEKLY/BIWEEKLY）
- bymonthday: 日 (1..31)（MONTHLY）
- skip_holidays: 日本の祝日（jpholiday）をスキップ
- active_from / active_until: 有効期間（active_until 無しは無期限）
- dest_offset_days / dest_time: 空車日から行先日時を相対計算

schedule（dict）の想定キー:
    freq, byday:[int], bymonthday:int,
    vacant_time, dest_offset_days, dest_time,
    active_from "YYYY-MM-DD", active_until "YYYY-MM-DD"|None,
    skip_holidays: bool
"""
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional

WEEKDAY_LABELS = ["月", "火", "水", "木", "金", "土", "日"]


def _parse(d) -> Optional[date]:
    if not d:
        return None
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_holiday(d: date) -> bool:
    """日本の祝日か（jpholiday 未導入でも落ちないよう握りつぶす）。"""
    try:
        import jpholiday
        return bool(jpholiday.is_holiday(d))
    except Exception:
        return False


def matches(schedule: Dict[str, Any], d: date) -> bool:
    """指定日 d がルールの発生日に該当するか（有効期間・祝日スキップ込み）。"""
    af = _parse(schedule.get("active_from"))
    au = _parse(schedule.get("active_until"))
    if af and d < af:
        return False
    if au and d > au:
        return False

    freq = (schedule.get("freq") or "").upper()
    if freq == "DAILY":
        ok = True
    elif freq in ("WEEKLY", "BIWEEKLY"):
        byday = [int(x) for x in (schedule.get("byday") or [])]
        ok = d.weekday() in byday
        if ok and freq == "BIWEEKLY":
            # active_from の週（月曜起点）をアンカーに、偶数週のみ発生
            anchor_base = af or d
            anchor_monday = anchor_base - timedelta(days=anchor_base.weekday())
            weeks = (d - anchor_monday).days // 7
            ok = (weeks % 2) == 0
    elif freq == "MONTHLY":
        ok = d.day == int(schedule.get("bymonthday") or 1)
    else:
        ok = False

    if not ok:
        return False
    if schedule.get("skip_holidays") and is_holiday(d):
        return False
    return True


def due_dates(schedule: Dict[str, Any], start: date, end: date) -> List[date]:
    """[start, end]（両端含む）でルールに該当する日付の一覧。"""
    out = []
    d = start
    while d <= end:
        if matches(schedule, d):
            out.append(d)
        d += timedelta(days=1)
    return out


def occurrence_to_posting(schedule: Dict[str, Any], vacant_date: date) -> Dict[str, Any]:
    """1発生日 → 空車1件分の truck_posting データ（vacant/dest 日時を確定）。"""
    offset = int(schedule.get("dest_offset_days") or 1)
    dest_date = vacant_date + timedelta(days=offset)
    return {
        "vacant_date": vacant_date.isoformat(),
        "vacant_time": schedule.get("vacant_time") or "09:00",
        "vacant_pref": schedule.get("vacant_pref"),
        "vacant_city": schedule.get("vacant_city"),
        "dest_date": dest_date.isoformat(),
        "dest_time": schedule.get("dest_time") or "09:00",
        "dest_pref": schedule.get("dest_pref"),
        "dest_city": schedule.get("dest_city"),
        "vacant_able_prefs": schedule.get("vacant_able_prefs") or [],
        "dest_able_prefs": schedule.get("dest_able_prefs") or [],
        "truck_weight": schedule.get("truck_weight") or "問わず",
        "vehicle_type": schedule.get("vehicle_type") or "問わず",
        "min_freight": schedule.get("min_freight"),
        "remarks": schedule.get("remarks") or "",
        "contact_name": schedule.get("contact_name"),
        "post_to_trabox": bool(schedule.get("post_to_trabox")),
        "post_to_webkit": bool(schedule.get("post_to_webkit")),
    }


def describe(schedule: Dict[str, Any]) -> str:
    """ルールを人間可読の文字列にする（例: 毎週 火・木 09:00 空車）。"""
    freq = (schedule.get("freq") or "").upper()
    t = schedule.get("vacant_time") or "09:00"
    if freq == "DAILY":
        base = "毎日"
    elif freq in ("WEEKLY", "BIWEEKLY"):
        days = "・".join(WEEKDAY_LABELS[int(x)] for x in (schedule.get("byday") or []))
        base = f"{'隔週' if freq == 'BIWEEKLY' else '毎週'} {days}"
    elif freq == "MONTHLY":
        base = f"毎月 {int(schedule.get('bymonthday') or 1)}日"
    else:
        base = "?"
    hol = "（祝日除く）" if schedule.get("skip_holidays") else ""
    return f"{base} {t} 空車{hol}"
