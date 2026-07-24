"""Firestore データアクセス層（SQLite からの移行先）

【設計方針】
- Cloud Run のインスタンスは使い捨てのため、永続データは Firestore に保存する。
  Firestore は無料枠が大きく、この規模なら実質 ¥0 かつデータ消失なし。
- 既存コードは整数IDに強く依存（URL /cases/{id} 等）するため、`counters`
  コレクションで**連番の整数ID**を採番して互換性を保つ。
- 案件検索は Firestore の複合クエリ制約（不等式は1フィールドまで）を避けるため、
  user_id（管理者は全件）で取得後に **Python 側でフィルタ**する。件数が少ない
  社内ツールのため十分高速。

【コレクション】
- users            : doc id = str(id)  {username,email,hashed_password,is_admin,created_at}
- credentials      : doc id = str(user_id) {trabox_*, webkit_person_id, contact_*, case_columns}
- cases            : doc id = str(id)  {user_id, pick_location, ..., contact_name(=登録者名), extras(map), created_at}
- posting_history  : doc id = str(id)  {case_id, platform, status, baggage_no, error_message, action, posted_at, updated_at}
- counters         : doc id = コレクション名 {seq: int}

ローカル開発では FIRESTORE_EMULATOR_HOST を設定してエミュレータに接続する。
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_JST = timezone(timedelta(hours=9))
_client = None


def _db():
    """Firestore クライアント（遅延初期化・シングルトン）"""
    global _client
    if _client is None:
        from google.cloud import firestore
        project = os.getenv("GCP_PROJECT_ID") or os.getenv(
            "GOOGLE_CLOUD_PROJECT", "carroo-test")
        _client = firestore.Client(project=project)
        logger.info(f"[Store] Firestore 接続: project={project} "
                    f"emulator={os.getenv('FIRESTORE_EMULATOR_HOST', '本番')}")
    return _client


def _now() -> str:
    """現在時刻（JST・'YYYY-MM-DD HH:MM:SS'）。SQLite の CURRENT_TIMESTAMP 相当"""
    return datetime.now(_JST).strftime("%Y-%m-%d %H:%M:%S")


def _next_id(name: str) -> int:
    """counters コレクションでトランザクション採番（連番の整数ID）"""
    from google.cloud import firestore
    db = _db()
    ref = db.collection("counters").document(name)

    @firestore.transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        cur = (snap.to_dict() or {}).get("seq", 0) if snap.exists else 0
        nxt = cur + 1
        txn.set(ref, {"seq": nxt})
        return nxt

    return _txn(db.transaction())


# ============ users ============

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    snap = _db().collection("users").document(str(user_id)).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    d["id"] = int(snap.id)
    return d


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    docs = _db().collection("users").where("username", "==", username).limit(1).stream()
    for snap in docs:
        d = snap.to_dict()
        d["id"] = int(snap.id)
        return d
    return None


def user_exists(username: str, email: str) -> bool:
    col = _db().collection("users")
    if any(col.where("username", "==", username).limit(1).stream()):
        return True
    if any(col.where("email", "==", email).limit(1).stream()):
        return True
    return False


def create_user(username: str, email: str, hashed_password: str,
                is_admin: bool = False) -> int:
    uid = _next_id("users")
    _db().collection("users").document(str(uid)).set({
        "username": username, "email": email,
        "hashed_password": hashed_password,
        "is_admin": bool(is_admin), "created_at": _now(),
    })
    return uid


def list_users() -> List[Dict[str, Any]]:
    out = []
    for snap in _db().collection("users").stream():
        d = snap.to_dict()
        d["id"] = int(snap.id)
        out.append(d)
    out.sort(key=lambda u: u["id"])
    return out


def delete_user(user_id: int) -> None:
    _db().collection("users").document(str(user_id)).delete()


def count_user_cases(user_id: int) -> int:
    return sum(1 for _ in _db().collection("cases")
               .where("user_id", "==", int(user_id)).stream())


# ============ credentials（初期設定） ============

def get_credentials(user_id: int) -> Dict[str, Any]:
    snap = _db().collection("credentials").document(str(user_id)).get()
    return snap.to_dict() if snap.exists else {}


def upsert_credentials(user_id: int, fields: Dict[str, Any]) -> None:
    """指定フィールドのみ更新（None は無視して既存を維持）"""
    data = {k: v for k, v in fields.items() if v is not None}
    if not data:
        return
    _db().collection("credentials").document(str(user_id)).set(data, merge=True)


# ============ cases ============

def create_case(user_id: int, data: Dict[str, Any], group_id: int = None,
                tenant_id: str = "takeuchi") -> int:
    cid = _next_id("cases")
    doc = dict(data)
    doc["user_id"] = int(user_id)
    doc["tenant_id"] = tenant_id   # Stage 0: マルチテナント対応レディ
    if group_id is not None:
        doc["group_id"] = int(group_id)  # 複数日程一括投稿のグループ束ね
    doc["created_at"] = _now()
    _db().collection("cases").document(str(cid)).set(doc)
    return cid


def next_group_id() -> int:
    """複数日程一括投稿のグループID採番。"""
    return _next_id("case_groups")


def list_group_cases(group_id: int, user_id: int = None) -> List[Dict[str, Any]]:
    """同一グループ（複数日程）の案件一覧。"""
    col = _db().collection("cases").where("group_id", "==", int(group_id))
    rows = []
    for s in col.stream():
        d = s.to_dict()
        if user_id is not None and int(d.get("user_id")) != int(user_id):
            continue
        d["id"] = int(s.id)
        rows.append(d)
    rows.sort(key=lambda c: c.get("pickup_date", ""))
    return rows


def get_case(case_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    snap = _db().collection("cases").document(str(case_id)).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    if user_id is not None and int(d.get("user_id")) != int(user_id):
        return None
    d["id"] = int(snap.id)
    return d


def update_case(case_id: int, user_id: int, fields: Dict[str, Any]) -> bool:
    ref = _db().collection("cases").document(str(case_id))
    snap = ref.get()
    if not snap.exists or int(snap.to_dict().get("user_id")) != int(user_id):
        return False
    ref.set(fields, merge=True)
    return True


def search_cases(is_admin: bool, user_id: int, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """案件検索。user_id（管理者は全件/指定ユーザー）で取得後 Python でフィルタ。

    filters: q_user, date_from, date_to, pick, drop, vehicle, registrant
    """
    col = _db().collection("cases")
    if is_admin:
        if filters.get("q_user"):
            docs = col.where("user_id", "==", int(filters["q_user"])).stream()
        else:
            docs = col.stream()
    else:
        docs = col.where("user_id", "==", int(user_id)).stream()

    rows = []
    for snap in docs:
        d = snap.to_dict()
        d["id"] = int(snap.id)
        rows.append(d)

    df, dt = filters.get("date_from"), filters.get("date_to")
    pick, drop = filters.get("pick"), filters.get("drop")
    veh, reg = filters.get("vehicle"), filters.get("registrant")

    def keep(c):
        pd = c.get("pickup_date") or ""
        if df and pd < df:
            return False
        if dt and pd > dt:
            return False
        if pick and not (c.get("pick_location") or "").startswith(pick):
            return False
        if drop and not (c.get("drop_location") or "").startswith(drop):
            return False
        if veh and (c.get("vehicle_type") or "") != veh:
            return False
        if reg and reg not in (c.get("contact_name") or ""):
            return False
        return True

    rows = [c for c in rows if keep(c)]
    rows.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return rows


def list_registrants(is_admin: bool, user_id: int) -> List[str]:
    """絞り込み用: 登録者名（contact_name）の一覧（重複除去）

    一般ユーザーは自分のアカウント内、管理者は全件。
    """
    col = _db().collection("cases")
    docs = (col.stream() if is_admin
            else col.where("user_id", "==", int(user_id)).stream())
    names = set()
    for snap in docs:
        n = (snap.to_dict().get("contact_name") or "").strip()
        if n:
            names.add(n)
    return sorted(names)


# ============ posting_history（追記式イベントログ） ============

def add_posting_event(case_id: int, platform: str, action: str,
                      status: str = "pending") -> int:
    hid = _next_id("posting_history")
    _db().collection("posting_history").document(str(hid)).set({
        "case_id": int(case_id), "platform": platform, "action": action,
        "status": status, "baggage_no": None, "error_message": None,
        "posted_at": _now(), "updated_at": None,
    })
    return hid


def update_posting_result(case_id: int, platform: str, status: str,
                          baggage_no: str = None, error_message: str = None,
                          action: str = None) -> None:
    """最新の該当イベント行を結果で更新（action指定時はそのactionの最新行）"""
    col = _db().collection("posting_history")
    q = col.where("case_id", "==", int(case_id)).where("platform", "==", platform)
    if action:
        q = q.where("action", "==", action)
    rows = sorted(q.stream(), key=lambda s: int(s.id), reverse=True)
    if not rows:
        return
    ref = rows[0].reference
    patch = {"status": status, "error_message": error_message,
             "updated_at": _now()}
    if baggage_no is not None:
        patch["baggage_no"] = baggage_no
    ref.set(patch, merge=True)


def get_active_baggage_no(case_id: int, platform: str) -> str:
    """現在有効な荷物番号/伝票番号（最新の成功した register/update）"""
    col = _db().collection("posting_history")
    rows = [s.to_dict() for s in col.where("case_id", "==", int(case_id))
            .where("platform", "==", platform).where("status", "==", "success").stream()]
    rows = [r for r in rows if r.get("action") in ("register", "update") and r.get("baggage_no")]
    rows.sort(key=lambda r: r.get("posted_at", ""), reverse=True)
    return rows[0]["baggage_no"] if rows else ""


def get_platform_state(case_id: int, platform: str) -> str:
    """live/deleted/working/error/none を最新イベントから判定"""
    col = _db().collection("posting_history")
    rows = sorted(
        col.where("case_id", "==", int(case_id)).where("platform", "==", platform).stream(),
        key=lambda s: int(s.id), reverse=True)
    if not rows:
        return "none"
    d = rows[0].to_dict()
    if d.get("status") == "pending":
        return "working"
    if d.get("status") == "error":
        return "error"
    return "deleted" if d.get("action") == "delete" else "live"


def list_posting_history(case_id: int) -> List[Dict[str, Any]]:
    col = _db().collection("posting_history")
    rows = []
    for s in col.where("case_id", "==", int(case_id)).stream():
        d = s.to_dict()
        d["id"] = int(s.id)
        rows.append(d)
    rows.sort(key=lambda r: r["id"], reverse=True)
    return rows


def count_posting_by_status(user_id: int, status: str) -> int:
    """ダッシュボード統計用: 自分の案件の投稿成功/失敗数"""
    case_ids = {int(s.id) for s in _db().collection("cases")
                .where("user_id", "==", int(user_id)).stream()}
    if not case_ids:
        return 0
    cnt = 0
    for s in _db().collection("posting_history").where("status", "==", status).stream():
        if s.to_dict().get("case_id") in case_ids:
            cnt += 1
    return cnt


def recent_cases(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    rows = search_cases(False, user_id, {})
    return rows[:limit]


def ensure_seed_admin(hash_password_fn) -> None:
    """初回起動時: 管理者アカウントが無ければ作成（SQLite版の startup 相当）"""
    if not get_user_by_username("管理者"):
        create_user("管理者", "hrt_takeuchi@takeuchiunso.com",
                    hash_password_fn("12341234@"), is_admin=True)
        logger.info("[Store] 既定の管理者アカウントを作成しました")


# ============================================================
# 空車（トラック空き）: 荷物と完全分離した並行データ層
#   コレクション: truck_postings（1回分の空車）/ truck_posting_history（投稿履歴）
#   ID は counters の "truck_postings" で採番（荷物 cases とは別系列）
# ============================================================

def create_truck(user_id: int, data: Dict[str, Any], tenant_id: str = "takeuchi") -> int:
    tid = _next_id("truck_postings")
    doc = dict(data)
    doc["user_id"] = int(user_id)
    doc["tenant_id"] = tenant_id   # Stage 0: マルチテナント対応レディ
    doc["created_at"] = _now()
    _db().collection("truck_postings").document(str(tid)).set(doc)
    return tid


def get_truck(truck_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    snap = _db().collection("truck_postings").document(str(truck_id)).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    if user_id is not None and int(d.get("user_id")) != int(user_id):
        return None
    d["id"] = int(snap.id)
    return d


def update_truck_doc(truck_id: int, user_id: int, fields: Dict[str, Any]) -> bool:
    ref = _db().collection("truck_postings").document(str(truck_id))
    snap = ref.get()
    if not snap.exists or int(snap.to_dict().get("user_id")) != int(user_id):
        return False
    ref.set(fields, merge=True)
    return True


def search_trucks(is_admin: bool, user_id: int, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """空車検索。荷物 search_cases と同様に user_id で取得後 Python でフィルタ。
    filters: q_user, date_from, date_to, vacant, dest, vehicle, registrant"""
    col = _db().collection("truck_postings")
    if is_admin:
        docs = (col.where("user_id", "==", int(filters["q_user"])).stream()
                if filters.get("q_user") else col.stream())
    else:
        docs = col.where("user_id", "==", int(user_id)).stream()
    rows = []
    for snap in docs:
        d = snap.to_dict()
        d["id"] = int(snap.id)
        rows.append(d)
    df, dt = filters.get("date_from"), filters.get("date_to")
    vac, dst = filters.get("vacant"), filters.get("dest")
    veh, reg = filters.get("vehicle"), filters.get("registrant")

    def keep(c):
        vd = c.get("vacant_date") or ""
        if df and vd < df:
            return False
        if dt and vd > dt:
            return False
        if vac and not (c.get("vacant_pref") or "").startswith(vac):
            return False
        if dst and not (c.get("dest_pref") or "").startswith(dst):
            return False
        if veh and (c.get("vehicle_type") or "") != veh:
            return False
        if reg and reg not in (c.get("contact_name") or ""):
            return False
        return True

    rows = [c for c in rows if keep(c)]
    rows.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return rows


def add_truck_event(truck_id: int, platform: str, action: str,
                    status: str = "pending") -> int:
    hid = _next_id("truck_posting_history")
    _db().collection("truck_posting_history").document(str(hid)).set({
        "truck_id": int(truck_id), "platform": platform, "action": action,
        "status": status, "baggage_no": None, "error_message": None,
        "posted_at": _now(), "updated_at": None,
    })
    return hid


def update_truck_result(truck_id: int, platform: str, status: str,
                        baggage_no: str = None, error_message: str = None,
                        action: str = None) -> None:
    col = _db().collection("truck_posting_history")
    q = col.where("truck_id", "==", int(truck_id)).where("platform", "==", platform)
    if action:
        q = q.where("action", "==", action)
    rows = sorted(q.stream(), key=lambda s: int(s.id), reverse=True)
    if not rows:
        return
    patch = {"status": status, "error_message": error_message, "updated_at": _now()}
    if baggage_no is not None:
        patch["baggage_no"] = baggage_no
    rows[0].reference.set(patch, merge=True)


def get_truck_active_baggage_no(truck_id: int, platform: str) -> str:
    col = _db().collection("truck_posting_history")
    rows = [s.to_dict() for s in col.where("truck_id", "==", int(truck_id))
            .where("platform", "==", platform).where("status", "==", "success").stream()]
    rows = [r for r in rows if r.get("action") in ("register", "update") and r.get("baggage_no")]
    rows.sort(key=lambda r: r.get("posted_at", ""), reverse=True)
    return rows[0]["baggage_no"] if rows else ""


def get_truck_platform_state(truck_id: int, platform: str) -> str:
    col = _db().collection("truck_posting_history")
    rows = sorted(
        col.where("truck_id", "==", int(truck_id)).where("platform", "==", platform).stream(),
        key=lambda s: int(s.id), reverse=True)
    if not rows:
        return "none"
    d = rows[0].to_dict()
    if d.get("status") == "pending":
        return "working"
    if d.get("status") == "error":
        return "error"
    return "deleted" if d.get("action") == "delete" else "live"


def list_truck_history(truck_id: int) -> List[Dict[str, Any]]:
    col = _db().collection("truck_posting_history")
    rows = []
    for s in col.where("truck_id", "==", int(truck_id)).stream():
        d = s.to_dict()
        d["id"] = int(s.id)
        rows.append(d)
    rows.sort(key=lambda r: r["id"], reverse=True)
    return rows


# ============================================================
# 繰り返しルール（truck_schedules）＋ マテリアライズ重複防止
#   Phase 2。Stage 0 として tenant_id を全書き込みに保持する。
# ============================================================

def create_schedule(user_id: int, data: Dict[str, Any], tenant_id: str = "takeuchi") -> int:
    sid = _next_id("truck_schedules")
    doc = dict(data)
    doc["user_id"] = int(user_id)
    doc["tenant_id"] = tenant_id
    doc["status"] = data.get("status", "active")
    doc["created_at"] = _now()
    _db().collection("truck_schedules").document(str(sid)).set(doc)
    return sid


def get_schedule(schedule_id: int, user_id: int = None) -> Optional[Dict[str, Any]]:
    snap = _db().collection("truck_schedules").document(str(schedule_id)).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    if user_id is not None and int(d.get("user_id")) != int(user_id):
        return None
    d["id"] = int(snap.id)
    return d


def update_schedule(schedule_id: int, user_id: int, fields: Dict[str, Any]) -> bool:
    ref = _db().collection("truck_schedules").document(str(schedule_id))
    snap = ref.get()
    if not snap.exists or int(snap.to_dict().get("user_id")) != int(user_id):
        return False
    ref.set(fields, merge=True)
    return True


def delete_schedule(schedule_id: int, user_id: int) -> bool:
    ref = _db().collection("truck_schedules").document(str(schedule_id))
    snap = ref.get()
    if not snap.exists or int(snap.to_dict().get("user_id")) != int(user_id):
        return False
    ref.delete()
    return True


def list_schedules(is_admin: bool, user_id: int) -> List[Dict[str, Any]]:
    col = _db().collection("truck_schedules")
    docs = col.stream() if is_admin else col.where("user_id", "==", int(user_id)).stream()
    rows = []
    for s in docs:
        d = s.to_dict()
        d["id"] = int(s.id)
        rows.append(d)
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows


def list_active_schedules(tenant_id: str = None) -> List[Dict[str, Any]]:
    """マテリアライズ対象＝status==active のルール（任意で tenant で絞る）。"""
    col = _db().collection("truck_schedules").where("status", "==", "active")
    if tenant_id:
        col = col.where("tenant_id", "==", tenant_id)
    rows = []
    for s in col.stream():
        d = s.to_dict()
        d["id"] = int(s.id)
        rows.append(d)
    return rows


def mark_materialized(schedule_id: int, vacant_date: str) -> bool:
    """(schedule_id, vacant_date) を「生成済み」として記録。
    まだ未生成なら True（今回生成すべき）、既に生成済みなら False を返す。
    doc id を一意キーにし、存在チェック→作成で冪等にする（日次・単一実行前提）。"""
    doc_id = f"{schedule_id}_{vacant_date}"
    ref = _db().collection("schedule_materialized").document(doc_id)
    if ref.get().exists:
        return False
    ref.set({"schedule_id": int(schedule_id), "vacant_date": vacant_date,
             "created_at": _now()})
    return True
