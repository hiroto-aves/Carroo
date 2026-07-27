"""管理者用ルーター

管理者のみアクセス可能:
- ユーザー管理（一覧・新規発行）
- （案件の横断検索はダッシュボードの案件一覧で is_admin により全件表示）
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.database import get_db_connection
from app.dependencies import get_current_user
from app.utils.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user: dict):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="この操作には管理者権限が必要です",
        )


def _dlq_badge() -> str:
    """未解決DLQ件数の赤バッジ（0なら非表示）。"""
    try:
        from app.db import store
        n = store.count_dead_letters()
    except Exception:
        n = 0
    if not n:
        return ""
    return (f'<span style="margin-left:5px;background:#C9503E;color:#fff;font-size:11px;'
            f'font-weight:700;padding:1px 7px;border-radius:999px">{n}</span>')


@router.get("/users", response_class=HTMLResponse)
async def users_page(current_user: dict = Depends(get_current_user)):
    """ユーザー管理画面（一覧＋新規発行フォーム）。管理者のみ。左レール・シェル。"""
    _require_admin(current_user)
    from app.db import store
    from app.ui_shell import render_page, esc
    users = [
        (u["id"], u["username"], u.get("email"), u.get("is_admin"),
         u.get("created_at"), store.count_user_cases(u["id"]))
        for u in store.list_users()
    ]

    rows = ""
    for uid, uname, email, is_admin, created, ncases in users:
        badge = ('<span class="chip met" style="margin-left:6px">管理者</span>'
                 if is_admin else '<span class="chip off" style="margin-left:6px">一般</span>')
        rows += f"""
        <tr>
          <td class="mono" style="color:var(--faint)">{uid}</td>
          <td style="font-weight:600">{esc(uname)}{badge}</td>
          <td style="color:var(--muted)">{esc(email)}</td>
          <td class="num" style="text-align:right">{ncases} 件</td>
          <td style="color:var(--faint)">{esc(created)}</td>
        </tr>"""

    body = f"""
  <h1 class="pt">ユーザー管理</h1>
  <p class="hl" style="margin:0 0 18px">社内ユーザーの一覧と、新規ユーザーの発行。
    · <a href="/admin/maintenance" style="color:var(--signal-ink);font-weight:600">🧹 データ整理</a>
    · <a href="/admin/dead-letters" style="color:var(--signal-ink);font-weight:600">☠️ 失敗タスク{_dlq_badge()}</a></p>

  <div class="card" style="overflow:hidden;margin-bottom:22px">
    <table>
      <thead><tr>
        <th>ID</th><th>ユーザー名</th><th>メール</th>
        <th style="text-align:right">登録案件</th><th>作成日</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <style>.uform input{{padding:12px 15px}}.uform input::placeholder{{color:var(--faint)}}</style>
  <div class="card" style="padding:22px;max-width:680px">
    <h2 style="font-size:16px;margin:0 0 16px">新しいユーザーを発行</h2>
    <form class="uform" method="post" action="/admin/users">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div><label class="fl">ユーザー名 *</label><input name="username" required placeholder="例: 山田太郎"></div>
        <div><label class="fl">メールアドレス *</label><input type="email" name="email" required placeholder="user@example.com"></div>
        <div><label class="fl">初期パスワード *</label><input name="password" required placeholder="4文字以上"></div>
        <div style="display:flex;align-items:flex-end"><label style="display:flex;gap:8px;align-items:center;font-size:13px;color:var(--ink)">
          <input type="checkbox" name="is_admin" value="yes" style="width:auto"> このユーザーも管理者にする</label></div>
      </div>
      <button type="submit" class="btn" style="margin-top:16px">ユーザーを発行</button>
      <p class="hl" style="margin:12px 0 0;font-size:12px">発行後、そのユーザーはメール（ユーザー名）と初期パスワードでログインし、初期設定画面で認証情報・連絡先を登録します。</p>
    </form>
  </div>"""

    return HTMLResponse(render_page(
        title="ユーザー管理", active="users", body=body, user=current_user,
        crumb="Carroo · 管理"))


@router.post("/users")
async def create_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """新規ユーザー発行（管理者のみ）"""
    _require_admin(current_user)
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="パスワードは4文字以上にしてください")
    from app.db import store
    if store.user_exists(username, email):
        raise HTTPException(
            status_code=400,
            detail="同じユーザー名またはメールが既に存在します",
        )
    store.create_user(username, email, hash_password(password),
                      is_admin=(is_admin == "yes"))
    from app.utils.audit import audit
    audit("user_create", new_username=username, is_admin=(is_admin == "yes"),
          by=current_user.get("username"))
    logger.info(f"[Admin] ユーザー発行: {username} (by {current_user['username']})")
    return RedirectResponse(url="/admin/users", status_code=302)


# ============ データ整理（テストダミー案件の完全削除）============

_UNSAFE = ("live", "working")  # 掲載中・処理中は削除不可（外部掲載が残るため）


def _case_states(case_id: int):
    from app.db import store
    tb = store.get_platform_state(case_id, "trabox")
    wk = store.get_platform_state(case_id, "webkit")
    return tb, wk, (tb not in _UNSAFE and wk not in _UNSAFE)


def _truck_states(truck_id: int):
    from app.db import store
    tb = store.get_truck_platform_state(truck_id, "trabox")
    wk = store.get_truck_platform_state(truck_id, "webkit")
    return tb, wk, (tb not in _UNSAFE and wk not in _UNSAFE)


@router.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(current_user: dict = Depends(get_current_user)):
    """全案件・全空車を一覧し、掲載の無いレコードを完全削除できる（管理者のみ）。"""
    _require_admin(current_user)
    from app.db import store
    from app.ui_shell import render_page, esc

    _badge = {"live": '<span class="chip live">掲載中</span>',
              "working": '<span class="chip wait">処理中</span>',
              "error": '<span class="chip off">エラー</span>',
              "deleted": '<span class="chip off">削除済</span>',
              "none": '<span class="chip off">なし</span>'}

    def _rows(items, states_fn, kind):
        html = ""
        n_purgeable = 0
        for it in items:
            iid = it["id"]
            tb, wk, purgeable = states_fn(iid)
            if purgeable:
                n_purgeable += 1
            if kind == "case":
                route = f"{it.get('pick_location','')} → {it.get('drop_location','')}"
            else:
                route = (f"{it.get('vacant_pref','')}{it.get('vacant_city','')} → "
                         f"{it.get('dest_pref','')}{it.get('dest_city','')}")
            btn = (f'<button class="btn danger" style="padding:5px 12px;font-size:12px" '
                   f'data-act="purge" data-args=\'["{kind}",{iid}]\'>完全削除</button>' if purgeable
                   else '<span class="hl" style="font-size:12px">掲載中は不可</span>')
            html += (f'<tr><td class="mono" style="color:var(--faint)">{iid}</td>'
                     f'<td>{esc(route)}</td><td style="color:var(--faint)">{esc(it.get("created_at",""))}</td>'
                     f'<td>{_badge.get(tb,tb)} {_badge.get(wk,wk)}</td>'
                     f'<td style="text-align:right">{btn}</td></tr>')
        return html or f'<tr><td colspan="5" style="text-align:center;color:var(--faint);padding:24px">{kind}はありません</td></tr>', n_purgeable

    cases = store.list_all_cases()
    trucks = store.list_all_trucks()
    case_rows, case_purge = _rows(cases, _case_states, "case")
    truck_rows, truck_purge = _rows(trucks, _truck_states, "truck")

    body = f"""
  <h1 class="pt">データ整理</h1>
  <p class="hl" style="margin:0 0 6px">テストダミー等、<b>掲載の無いレコードを完全削除</b>します。掲載中・処理中は外部掲載が残るため削除できません。</p>
  <div style="background:var(--amber-wash);border:1px solid var(--line-soft);border-radius:12px;padding:12px 14px;font-size:13px;color:var(--amber);margin:0 0 18px">
    ⚠️ 完全削除は<b>取り消せません</b>（Firestore の案件/空車レコード＋投稿履歴を物理削除）。掲載中の外部投稿には影響しません。
  </div>

  <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
    <button class="btn danger" data-act="purgeSafe" data-args='["case"]'>案件の掲載なし {case_purge}件を一括削除</button>
    <button class="btn danger" data-act="purgeSafe" data-args='["truck"]'>空車の掲載なし {truck_purge}件を一括削除</button>
  </div>

  <h2 style="font-size:15px;margin:18px 0 8px">案件（{len(cases)}件）</h2>
  <div class="card" style="overflow:hidden;margin-bottom:22px"><table>
    <thead><tr><th>ID</th><th>経路</th><th>登録日</th><th>掲載状態(トラ/WebKit)</th><th></th></tr></thead>
    <tbody>{case_rows}</tbody></table></div>

  <h2 style="font-size:15px;margin:18px 0 8px">空車（{len(trucks)}件）</h2>
  <div class="card" style="overflow:hidden"><table>
    <thead><tr><th>ID</th><th>経路</th><th>登録日</th><th>掲載状態(トラ/WebKit)</th><th></th></tr></thead>
    <tbody>{truck_rows}</tbody></table></div>

<script>
async function purge(kind,id){{
  if(!confirm('レコード#'+id+' を完全削除します。取り消せません。よろしいですか？'))return;
  const r=await fetch('/admin/maintenance/purge/'+kind+'/'+id,{{method:'POST'}});
  const j=await r.json();
  if(r.ok) location.reload(); else alert('エラー: '+(j.detail||'失敗'));
}}
async function purgeSafe(kind){{
  if(!confirm(kind+' の「掲載なし」レコードを一括で完全削除します。取り消せません。よろしいですか？'))return;
  const r=await fetch('/admin/maintenance/purge-safe/'+kind,{{method:'POST'}});
  const j=await r.json();
  if(r.ok){{ alert(j.deleted+'件を削除しました'); location.reload(); }} else alert('エラー: '+(j.detail||'失敗'));
}}
</script>"""
    return HTMLResponse(render_page(title="データ整理", active="users", body=body,
                                    user=current_user, crumb="Carroo · 管理"))


@router.post("/maintenance/purge/{kind}/{item_id}")
async def purge_one(kind: str, item_id: int,
                    current_user: dict = Depends(get_current_user)):
    """1レコードを完全削除（掲載中・処理中は拒否）。"""
    _require_admin(current_user)
    from app.db import store
    from app.utils.audit import audit
    if kind == "case":
        _, _, purgeable = _case_states(item_id)
        if not purgeable:
            raise HTTPException(400, "掲載中・処理中の案件は削除できません")
        res = store.purge_case(item_id)
    elif kind == "truck":
        _, _, purgeable = _truck_states(item_id)
        if not purgeable:
            raise HTTPException(400, "掲載中・処理中の空車は削除できません")
        res = store.purge_truck(item_id)
    else:
        raise HTTPException(400, "種別が不正です")
    audit("record_purge", kind=kind, item_id=item_id, by=current_user.get("username"))
    return {"status": "purged", "detail": res}


@router.post("/maintenance/purge-safe/{kind}")
async def purge_safe(kind: str, current_user: dict = Depends(get_current_user)):
    """掲載の無い（live/working でない）レコードを一括完全削除。"""
    _require_admin(current_user)
    from app.db import store
    from app.utils.audit import audit
    deleted = 0
    if kind == "case":
        for it in store.list_all_cases():
            if _case_states(it["id"])[2]:
                store.purge_case(it["id"]); deleted += 1
    elif kind == "truck":
        for it in store.list_all_trucks():
            if _truck_states(it["id"])[2]:
                store.purge_truck(it["id"]); deleted += 1
    else:
        raise HTTPException(400, "種別が不正です")
    audit("record_purge_bulk", kind=kind, deleted=deleted, by=current_user.get("username"))
    return {"status": "ok", "deleted": deleted}


# ============ Dead Letter Queue（確定失敗タスクの確認・再投稿）============

@router.get("/dead-letters", response_class=HTMLResponse)
async def dead_letters_page(current_user: dict = Depends(get_current_user)):
    """3回リトライしても失敗が確定した投稿タスクの一覧。再投稿／解決ができる（管理者のみ）。"""
    _require_admin(current_user)
    from app.db import store
    from app.ui_shell import render_page, esc
    items = store.list_dead_letters(include_resolved=False)
    rows = ""
    for d in items:
        p = d.get("payload") or {}
        cd = (p.get("case_data") or {})
        tgt = cd.get("case_id") or p.get("case_id") or p.get("truck_id") or "-"
        route = (f"{cd.get('pick_location','')} → {cd.get('drop_location','')}"
                 if cd else f"{(p.get('truck_data') or {}).get('vacant_pref','')}…")
        rows += (f'<tr><td class="mono" style="color:var(--faint)">#{d["id"]}</td>'
                 f'<td style="color:var(--faint);white-space:nowrap">{esc(d.get("created_at",""))}</td>'
                 f'<td>{esc(d.get("kind","case"))} / {esc(d.get("action","register"))}</td>'
                 f'<td class="mono">{esc(tgt)}</td><td>{esc(route)}</td>'
                 f'<td style="max-width:280px;color:var(--amber);font-size:12px">{esc((d.get("error") or "")[:160])}</td>'
                 f'<td style="text-align:right;white-space:nowrap">'
                 f'<button class="btn" style="padding:5px 12px;font-size:12px" data-act="dlqRetry" data-args="[{d["id"]}]">再投稿</button>'
                 f'<button class="btn ghost" style="padding:5px 12px;font-size:12px;margin-left:6px" data-act="dlqResolve" data-args="[{d["id"]}]">解決済み</button>'
                 f'</td></tr>')
    if not rows:
        rows = ('<tr><td colspan="7" style="text-align:center;color:var(--faint);padding:28px">'
                '未解決の失敗タスクはありません 🎉</td></tr>')
    body = f"""
  <h1 class="pt">失敗タスク（DLQ）</h1>
  <p class="hl" style="margin:0 0 6px">3回再試行しても投稿できなかったタスクです。原因を直したら「再投稿」、対応不要なら「解決済み」に。</p>
  <p class="hl" style="margin:0 0 16px">· <a href="/admin/users" style="color:var(--signal-ink)">ユーザー管理</a> · <a href="/admin/maintenance" style="color:var(--signal-ink)">データ整理</a></p>
  <div class="card" style="overflow-x:auto"><table>
    <thead><tr><th>ID</th><th>発生</th><th>種別</th><th>対象</th><th>経路</th><th>エラー</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table></div>
<script>
async function dlqRetry(id){{ if(!confirm('この失敗タスクを再投稿しますか？'))return;
  var r=await fetch('/admin/dead-letters/'+id+'/retry',{{method:'POST'}}); var j=await r.json();
  if(r.ok) location.reload(); else alert('エラー: '+(j.detail||'失敗')); }}
async function dlqResolve(id){{ if(!confirm('このタスクを解決済みにして一覧から消しますか？（再投稿はしません）'))return;
  var r=await fetch('/admin/dead-letters/'+id+'/resolve',{{method:'POST'}});
  if(r.ok) location.reload(); else alert('失敗'); }}
</script>"""
    return HTMLResponse(render_page(title="失敗タスク（DLQ）", active="users", body=body,
                                    user=current_user, crumb="Carroo · 管理"))


@router.post("/dead-letters/{did}/retry")
async def dead_letter_retry(did: int, current_user: dict = Depends(get_current_user)):
    """退避した元 payload をそのままキューへ再投入し、DLQ項目を解決済みにする。"""
    _require_admin(current_user)
    from app.db import store
    from app.services.cloud_tasks import get_task_client
    from app.utils.audit import audit
    d = store.get_dead_letter(did)
    if not d or d.get("resolved"):
        raise HTTPException(404, "対象の失敗タスクが見つかりません")
    payload = d.get("payload")
    if not payload:
        raise HTTPException(400, "再投稿に必要なデータがありません")
    get_task_client().add_task(payload)
    store.resolve_dead_letter(did, note="retried")
    audit("dead_letter_retry", dead_letter_id=did, by=current_user.get("username"))
    return {"status": "requeued", "dead_letter_id": did}


@router.post("/dead-letters/{did}/resolve")
async def dead_letter_resolve(did: int, current_user: dict = Depends(get_current_user)):
    """再投稿せず解決済みにする（手動対応済み・不要など）。"""
    _require_admin(current_user)
    from app.db import store
    from app.utils.audit import audit
    if not store.get_dead_letter(did):
        raise HTTPException(404, "対象の失敗タスクが見つかりません")
    store.resolve_dead_letter(did, note="dismissed")
    audit("dead_letter_resolve", dead_letter_id=did, by=current_user.get("username"))
    return {"status": "resolved"}
