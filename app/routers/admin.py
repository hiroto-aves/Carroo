"""管理者用ルーター

管理者のみアクセス可能:
- ユーザー管理（一覧・新規発行）
- （案件の横断検索はダッシュボードの案件一覧で is_admin により全件表示）
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.db.database import get_db_connection
from app.dependencies import get_current_user
from app.utils.security import hash_password
from app.tenancy import scope_tenant

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
    # owner は自テナントのみ／運営者(super)は全ユーザー
    _tid = None if current_user.get("is_super") else current_user.get("tenant_id")
    users = store.list_users(tenant_id=_tid)

    rows = ""
    for u in users:
        uid = u["id"]
        is_admin = u.get("is_admin")
        badge = ('<span class="chip met" style="margin-left:6px">管理者</span>'
                 if is_admin else '<span class="chip off" style="margin-left:6px">一般</span>')
        sup = ('<span class="chip live" style="margin-left:4px">運営</span>'
               if u.get("is_super") else "")
        ncases = store.count_user_cases(uid)
        # 自分自身・運営者は削除不可。運営者(super)は誰でも削除可（自分以外）。
        can_del = uid != current_user["id"] and (current_user.get("is_super") or not u.get("is_super"))
        del_btn = (f'<button class="btn danger" style="padding:4px 11px;font-size:12px" '
                   f'data-act="delUser" data-args=\'[{uid},"{esc(u.get("username",""))}"]\'>削除</button>'
                   if can_del else '<span class="hl" style="font-size:12px">—</span>')
        # 自分以外のパスワードを再設定可（自分は /auth/me から自分で変更）
        pw_btn = (f'<button class="btn ghost" style="padding:4px 11px;font-size:12px" '
                  f'data-act="resetPw" data-args=\'[{uid},"{esc(u.get("username",""))}"]\'>PW再設定</button>'
                  if uid != current_user["id"] else '')
        rows += f"""
        <tr>
          <td class="mono" style="color:var(--faint)">{uid}</td>
          <td style="font-weight:600">{esc(u.get("username",""))}{badge}{sup}</td>
          <td style="color:var(--muted)">{esc(u.get("email"))}</td>
          <td class="num" style="text-align:right">{ncases} 件</td>
          <td style="color:var(--faint)">{esc(u.get("created_at"))}</td>
          <td style="text-align:right;white-space:nowrap">{pw_btn} {del_btn}</td>
        </tr>"""

    # 課金の基礎: 有効ユーザー数（2人目以降が従量課金）
    seat_note = ""
    if not current_user.get("is_super"):
        n = len(users)
        seat_note = (f'<span style="color:var(--faint)"> ・ 現在のユーザー数 <b style="color:var(--ink)">{n}</b>'
                     f'（1人目は基本料に含む／2人目以降が従量課金）</span>')

    body = f"""
  <h1 class="pt">ユーザー管理</h1>
  <p class="hl" style="margin:0 0 18px">社内ユーザーの一覧と、新規ユーザーの発行。{seat_note}
    · <a href="/admin/maintenance" style="color:var(--signal-ink);font-weight:600">🧹 データ整理</a>
    · <a href="/failed/" style="color:var(--signal-ink);font-weight:600">☠️ 失敗した投稿{_dlq_badge()}</a></p>

  <div class="card" style="overflow:hidden;margin-bottom:22px">
    <table>
      <thead><tr>
        <th>ID</th><th>ユーザー名</th><th>メール</th>
        <th style="text-align:right">登録案件</th><th>作成日</th><th></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <script>
  async function delUser(id, name){{
    if(!confirm('ユーザー「'+name+'」を削除しますか？（このユーザーはログインできなくなります。登録した案件は残ります）'))return;
    var r=await fetch('/admin/users/'+id+'/delete',{{method:'POST'}});
    if(r.ok) location.reload(); else {{ var j=await r.json(); alert('エラー: '+(j.detail||'失敗')); }}
  }}
  async function resetPw(id, name){{
    var pw=prompt('「'+name+'」の新しいパスワードを入力してください（4文字以上）');
    if(!pw)return;
    var r=await fetch('/admin/users/'+id+'/reset-password',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{password:pw}})}});
    if(r.ok) alert('パスワードを再設定しました'); else {{ var j=await r.json(); alert('エラー: '+(j.detail||'失敗')); }}
  }}
  </script>

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
    # 発行先テナント＝発行者のテナント（運営者は既定テナントに発行）。super は付与しない。
    tenant_id = current_user.get("tenant_id") or "takeuchi"
    # 契約シート数の上限チェック（課金稼働時）。超える場合はお支払い画面でシート追加が必要。
    from app.services import billing
    if billing.billing_enabled():
        tenant = store.get_tenant(tenant_id) or {}
        cap = tenant.get("seat_limit")
        cap = cap if cap is not None else 1
        used = store.count_tenant_users(tenant_id)
        if used >= cap:
            raise HTTPException(
                status_code=400,
                detail=f"契約シート数（{cap}人）に達しています。『お支払い』画面でシートを追加してから発行してください。",
            )
    make_admin = (is_admin == "yes")
    store.create_user(username, email, hash_password(password),
                      is_admin=make_admin, tenant_id=tenant_id,
                      role=("owner" if make_admin else "member"), is_super=False)
    from app.utils.audit import audit
    audit("user_create", new_username=username, is_admin=make_admin,
          tenant_id=tenant_id, by=current_user.get("username"))
    logger.info(f"[Admin] ユーザー発行: {username} (by {current_user['username']})")
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{target_id}/delete")
async def delete_user_route(target_id: int,
                            current_user: dict = Depends(get_current_user)):
    """ユーザー削除（owner=自テナントのみ・自分と運営者は不可／super=自分以外可）。
    削除後にテナントの seats を再同期（課金反映）。"""
    _require_admin(current_user)
    from app.db import store
    from app.utils.audit import audit
    if target_id == current_user["id"]:
        raise HTTPException(400, "自分自身は削除できません")
    target = store.get_user_by_id(target_id)
    if not target:
        raise HTTPException(404, "ユーザーが見つかりません")
    is_super = current_user.get("is_super")
    if not is_super:
        # owner: 自テナントのみ・運営者ユーザーは消せない
        if (target.get("tenant_id") or "takeuchi") != current_user.get("tenant_id"):
            raise HTTPException(403, "他テナントのユーザーは削除できません")
        if target.get("is_super"):
            raise HTTPException(403, "運営者ユーザーは削除できません")
    store.delete_user(target_id)
    audit("user_delete", target_id=target_id,
          target_username=target.get("username"), by=current_user.get("username"))
    return {"status": "deleted"}


class PasswordReset(BaseModel):
    password: str


@router.post("/users/{target_id}/reset-password")
async def reset_user_password_route(target_id: int, data: PasswordReset,
                                    current_user: dict = Depends(get_current_user)):
    """メンバーのパスワードを管理者が再設定（owner=自テナントのみ・super=誰でも可）。自分自身は不可。"""
    _require_admin(current_user)
    from app.db import store
    from app.utils.audit import audit
    if target_id == current_user["id"]:
        raise HTTPException(400, "自分自身のパスワードは「アカウント」画面から変更してください")
    target = store.get_user_by_id(target_id)
    if not target:
        raise HTTPException(404, "ユーザーが見つかりません")
    if not current_user.get("is_super"):
        if (target.get("tenant_id") or "takeuchi") != current_user.get("tenant_id"):
            raise HTTPException(403, "他テナントのユーザーは操作できません")
    if len(data.password) < 4:
        raise HTTPException(400, "パスワードは4文字以上にしてください")
    store.set_user_password(target_id, hash_password(data.password))
    audit("user_password_reset", target_id=target_id,
          target_username=target.get("username"), by=current_user.get("username"))
    return {"status": "ok"}


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

    cases = store.list_all_cases(scope_tenant(current_user))
    trucks = store.list_all_trucks(scope_tenant(current_user))
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
        for it in store.list_all_cases(scope_tenant(current_user)):
            if _case_states(it["id"])[2]:
                store.purge_case(it["id"]); deleted += 1
    elif kind == "truck":
        for it in store.list_all_trucks(scope_tenant(current_user)):
            if _truck_states(it["id"])[2]:
                store.purge_truck(it["id"]); deleted += 1
    else:
        raise HTTPException(400, "種別が不正です")
    audit("record_purge_bulk", kind=kind, deleted=deleted, by=current_user.get("username"))
    return {"status": "ok", "deleted": deleted}

