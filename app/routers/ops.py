"""運営コンソール（/ops）— 運営者(super)専用。

テナント（会社）の発行・プラン設定・シート確認。将来 Stripe 連携の管理面もここ。
一般ユーザー/会社管理者(owner)はアクセス不可（403）。
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.db import store
from app.dependencies import get_current_user
from app.ui_shell import render_page, esc
from app.utils.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ops", tags=["ops"])

_PLANS = ["standard", "pro"]
# 個別付与できる Pro 機能（key, ラベル）
_GRANTABLE = [("recurring", "空車定期登録"), ("multidate", "複数日程"), ("reregister", "履歴から再登録")]


def _require_super(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_super"):
        raise HTTPException(403, "運営コンソールは運営者のみアクセスできます")
    return current_user


def _users_panel(current_user: dict) -> str:
    """全ユーザー一覧＋機能の個別付与＋ユーザー単位のデータ閲覧（運営者専用）。"""
    users = store.list_users()  # 全テナント横断
    rows = ""
    for u in users:
        uid = u["id"]
        feats = u.get("features") or {}
        checks = ""
        for key, label in _GRANTABLE:
            ck = " checked" if feats.get(key) else ""
            checks += (f'<label style="display:inline-flex;gap:4px;align-items:center;font-size:12px;margin-right:10px">'
                       f'<input type="checkbox" name="feat" value="{key}"{ck} style="width:auto"> {esc(label)}</label>')
        is_sup = u.get("is_super")
        sup = ' <span class="chip live" style="font-size:10px">運営</span>' if is_sup else ""
        # 運営者ON/OFF トグル
        if is_sup:
            sup_toggle = (f'<form method="post" action="/ops/users/{uid}/super">'
                          f'<input type="hidden" name="value" value="0">'
                          f'<button class="btn ghost" style="padding:4px 10px;font-size:12px" type="submit">運営者を外す</button></form>')
        else:
            sup_toggle = (f'<form method="post" action="/ops/users/{uid}/super">'
                          f'<input type="hidden" name="value" value="1">'
                          f'<button class="btn ghost" style="padding:4px 10px;font-size:12px" type="submit">運営者にする</button></form>')
        rows += (
          f'<tr><td class="mono" style="color:var(--faint)">{uid}</td>'
          f'<td style="font-weight:600">{esc(u.get("username",""))}{sup}</td>'
          f'<td style="color:var(--faint)">{esc(u.get("tenant_id") or "-")}</td>'
          f'<td style="color:var(--faint)">{esc(u.get("role") or "-")}</td>'
          f'<td><form method="post" action="/ops/users/{uid}/features" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
          f'{checks}<button class="btn ghost" style="padding:4px 10px;font-size:12px" type="submit">保存</button></form></td>'
          f'<td>{sup_toggle}</td>'
          f'<td style="text-align:right;white-space:nowrap">'
          f'<a href="/dashboard/cases?q_user={uid}" style="color:var(--signal-ink);font-size:12px">案件</a>'
          + (f' <button class="btn danger" style="padding:3px 9px;font-size:11px;margin-left:8px" '
             f'data-act="opsDelUser" data-args=\'[{uid},"{esc(u.get("username",""))}"]\'>削除</button>'
             if uid != current_user["id"] else '')
          + '</td></tr>')
    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;color:var(--faint);padding:20px">ユーザーがいません</td></tr>'
    opts_users = "".join(
        f'<option value="{u["id"]}">#{u["id"]} {esc(u.get("username",""))}'
        f'（{esc(u.get("tenant_id") or "-")}）</option>' for u in users)
    return f"""
  <h2 style="font-size:16px;margin:26px 0 4px">ユーザー別 機能付与・運営者権限・データ閲覧（運営者のみ）</h2>
  <p class="hl" style="margin:0 0 12px;font-size:12.5px">Pro機能を<b>1ユーザー単位で付与</b>／<b>運営者(super)権限のON/OFF</b>／「案件」でデータ閲覧。</p>
  <div class="card" style="padding:16px 18px;max-width:720px;margin-bottom:14px">
    <h3 style="font-size:14px;margin:0 0 10px">運営者アカウントを発行（竹内の管理者と分ける用）</h3>
    <form method="post" action="/ops/operators">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
        <div><label class="fl">ユーザー名 *</label><input name="username" required placeholder="例: 運営"></div>
        <div><label class="fl">メール *</label><input type="email" name="email" required placeholder="ops@example.com"></div>
        <div><label class="fl">初期パスワード *</label><input name="password" required placeholder="4文字以上"></div>
      </div>
      <button type="submit" class="btn" style="margin-top:12px">運営者を発行</button>
      <p class="hl" style="margin:10px 0 0;font-size:12px">発行後、その運営者でログイン → この一覧で竹内の管理者の「運営者を外す」を押すと、権限がきれいに分かれます。</p>
    </form>
  </div>
  <div class="card" style="overflow-x:auto;margin-bottom:14px"><table>
    <thead><tr><th>ID</th><th>ユーザー</th><th>テナント</th><th>ロール</th><th>個別機能付与</th><th>運営者</th><th>データ</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <div class="card" style="padding:16px 18px;max-width:720px;margin-bottom:22px">
    <h3 style="font-size:14px;margin:0 0 4px">🔑 ユーザーのログイン情報を修正（パスワード再設定）</h3>
    <p class="hl" style="margin:0 0 12px;font-size:12px">ログインできなくなったユーザーの復旧に。空欄の項目は変更しません。</p>
    <form method="post" action="/ops/users/credentials">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div><label class="fl">対象ユーザー *</label><select name="user_id" required>{opts_users}</select></div>
        <div><label class="fl">新しいパスワード</label><input name="password" placeholder="空欄なら変更しない"></div>
        <div><label class="fl">新しいユーザー名</label><input name="username" placeholder="空欄なら変更しない"></div>
        <div><label class="fl">新しいメール</label><input type="email" name="email" placeholder="空欄なら変更しない"></div>
      </div>
      <button type="submit" class="btn" style="margin-top:12px">保存する</button>
    </form>
  </div>"""


@router.get("/", response_class=HTMLResponse)
async def ops_home(current_user: dict = Depends(_require_super)):
    tenants = store.list_tenants()
    rows = ""
    for t in tenants:
        tid = t["id"]
        plan = t.get("plan") or "standard"
        seats = t.get("seats", 0)
        status = t.get("subscription_status") or "—"
        plan_sel = "".join(
            f'<option value="{p}"{" selected" if p == plan else ""}>{p}</option>' for p in _PLANS)
        rows += (
            f'<tr><td class="mono" style="color:var(--faint)">{esc(tid)}</td>'
            f'<td style="font-weight:600">{esc(t.get("name",""))}</td>'
            f'<td><form method="post" action="/ops/tenants/{esc(tid)}/plan" style="display:flex;gap:6px;align-items:center">'
            f'<select name="plan" style="width:auto;padding:5px 8px;font-size:13px">{plan_sel}</select>'
            f'<button class="btn ghost" style="padding:5px 11px;font-size:12px" type="submit">変更</button></form></td>'
            f'<td class="num" style="text-align:right">{seats}</td>'
            f'<td style="color:var(--faint)">{esc(status)}</td>'
            f'<td style="color:var(--faint)">{esc(t.get("created_at",""))}</td></tr>')
    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;color:var(--faint);padding:24px">テナントがありません</td></tr>'

    plan_opts = "".join(f'<option value="{p}">{p}</option>' for p in _PLANS)
    body = f"""
  <h1 class="pt">運営コンソール</h1>
  <p class="hl" style="margin:0 0 18px">テナント（会社）の発行・プラン設定・シート確認。運営者専用。</p>

  <div class="card" style="overflow-x:auto;margin-bottom:22px"><table>
    <thead><tr><th>テナントID</th><th>会社名</th><th>プラン</th>
      <th style="text-align:right">シート</th><th>課金状態</th><th>作成日</th></tr></thead>
    <tbody>{rows}</tbody></table></div>

  {_users_panel(current_user)}

  <div class="card" style="padding:22px;max-width:720px">
    <h2 style="font-size:16px;margin:0 0 4px">新しいテナントを発行</h2>
    <p class="hl" style="margin:0 0 16px;font-size:12.5px">テナントIDは英小文字・数字（例: takeuchi）。最初の管理者ユーザーも同時に作成します。</p>
    <form method="post" action="/ops/tenants">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
        <div><label class="fl">テナントID *</label><input name="tenant_id" required placeholder="例: sample-co"></div>
        <div><label class="fl">会社名 *</label><input name="name" required placeholder="例: サンプル運送"></div>
        <div><label class="fl">プラン</label><select name="plan">{plan_opts}</select></div>
        <div></div>
        <div style="grid-column:1/-1;border-top:1px solid var(--line-soft);margin-top:6px;padding-top:12px;font-size:12.5px;color:var(--faint)">最初の管理者ユーザー（owner）</div>
        <div><label class="fl">ユーザー名 *</label><input name="admin_username" required placeholder="例: 管理者"></div>
        <div><label class="fl">メール *</label><input type="email" name="admin_email" required placeholder="admin@example.com"></div>
        <div><label class="fl">初期パスワード *</label><input name="admin_password" required placeholder="4文字以上"></div>
      </div>
      <button type="submit" class="btn" style="margin-top:16px">テナントを発行</button>
    </form>
  </div>
<script>
async function opsDelUser(id, name){{
  if(!confirm('ユーザー「'+name+'」を完全に削除しますか？（ログインできなくなります。取り消せません）'))return;
  var r=await fetch('/ops/users/'+id+'/delete',{{method:'POST'}});
  if(r.ok) location.reload(); else {{ var j=await r.json(); alert('エラー: '+(j.detail||'失敗')); }}
}}
</script>"""
    return HTMLResponse(render_page(title="運営コンソール", active="ops", body=body,
                                    user=current_user, crumb="Carroo · 運営"))


@router.post("/tenants")
async def create_tenant_route(
    tenant_id: str = Form(...), name: str = Form(...), plan: str = Form("standard"),
    admin_username: str = Form(...), admin_email: str = Form(...),
    admin_password: str = Form(...),
    current_user: dict = Depends(_require_super),
):
    from app.utils.audit import audit
    tid = (tenant_id or "").strip().lower()
    if not tid:
        raise HTTPException(400, "テナントIDは必須です")
    if store.get_tenant(tid):
        raise HTTPException(400, "そのテナントIDは既に存在します")
    if plan not in _PLANS:
        plan = "standard"
    if len(admin_password) < 4:
        raise HTTPException(400, "初期パスワードは4文字以上にしてください")
    if store.user_exists(admin_username, admin_email):
        raise HTTPException(400, "同じユーザー名またはメールが既に存在します")
    store.create_tenant(tid, name.strip(), plan=plan)
    store.create_user(admin_username, admin_email, hash_password(admin_password),
                      is_admin=True, tenant_id=tid, role="owner", is_super=False)
    audit("tenant_create", tenant_id=tid, plan=plan, by=current_user.get("username"))
    logger.info(f"[Ops] テナント発行: {tid} plan={plan}")
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)


@router.post("/operators")
async def create_operator_route(
    username: str = Form(...), email: str = Form(...), password: str = Form(...),
    current_user: dict = Depends(_require_super),
):
    """運営者(super)アカウントを発行。運営用テナント carroo-ops に所属。"""
    from app.utils.audit import audit
    if len(password) < 4:
        raise HTTPException(400, "初期パスワードは4文字以上にしてください")
    if store.user_exists(username, email):
        raise HTTPException(400, "同じユーザー名またはメールが既に存在します")
    ops_tid = "carroo-ops"
    if not store.get_tenant(ops_tid):
        store.create_tenant(ops_tid, "Carroo 運営", plan="pro")
    store.create_user(username, email, hash_password(password),
                      is_admin=True, tenant_id=ops_tid, role="owner", is_super=True)
    audit("operator_create", new_username=username, by=current_user.get("username"))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)


@router.post("/users/{user_id}/super")
async def set_user_super_route(user_id: int, value: str = Form("0"),
                               current_user: dict = Depends(_require_super)):
    """運営者(super)権限の付与/剥奪。自分自身の剥奪は不可（ロックアウト防止）。"""
    from app.utils.audit import audit
    if not store.get_user_by_id(user_id):
        raise HTTPException(404, "ユーザーが見つかりません")
    make = value in ("1", "yes", "true", "on")
    if not make and user_id == current_user["id"]:
        raise HTTPException(400, "自分自身の運営者権限は外せません（別の運営者アカウントから操作してください）")
    store.set_user_super(user_id, make)
    audit("user_super_set", target_id=user_id, is_super=make, by=current_user.get("username"))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)


@router.post("/users/{user_id}/delete")
async def ops_delete_user(user_id: int, current_user: dict = Depends(_require_super)):
    """運営者が任意ユーザーを削除（テナント不問）。自分自身は不可。"""
    from app.utils.audit import audit
    if user_id == current_user["id"]:
        raise HTTPException(400, "自分自身は削除できません")
    target = store.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, "ユーザーが見つかりません")
    store.delete_user(user_id)
    audit("ops_user_delete", target_id=user_id,
          target_username=target.get("username"), by=current_user.get("username"))
    return {"status": "deleted"}


@router.post("/users/credentials")
async def ops_set_credentials(
    user_id: int = Form(...), username: str = Form(""), email: str = Form(""),
    password: str = Form(""), current_user: dict = Depends(_require_super),
):
    """運営者が任意ユーザーのログイン情報を再設定（ロックアウト復旧）。空欄は変更なし。"""
    from app.utils.audit import audit
    target = store.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, "ユーザーが見つかりません")
    new_username = (username or "").strip() or target.get("username")
    new_email = (email or "").strip() or target.get("email")
    conflict = store.account_conflict(user_id, new_username, new_email)
    if conflict:
        raise HTTPException(400, conflict)
    store.update_user_account(user_id, username=new_username, email=new_email)
    if password:
        if len(password) < 4:
            raise HTTPException(400, "パスワードは4文字以上にしてください")
        store.set_user_password(user_id, hash_password(password))
    audit("ops_reset_credentials", target_id=user_id, by=current_user.get("username"))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)


@router.post("/users/{user_id}/features")
async def set_user_features_route(user_id: int, request: Request,
                                  current_user: dict = Depends(_require_super)):
    """ユーザー個別の機能付与を保存（チェックした機能を true で付与・他は継承）。"""
    from app.utils.audit import audit
    form = await request.form()
    checked = set(form.getlist("feat"))
    valid = {k for k, _ in _GRANTABLE}
    features = {k: True for k in checked if k in valid}
    if not store.get_user_by_id(user_id):
        raise HTTPException(404, "ユーザーが見つかりません")
    store.set_user_features(user_id, features)
    audit("user_features_set", target_id=user_id, features=list(features.keys()),
          by=current_user.get("username"))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)


@router.post("/tenants/{tenant_id}/plan")
async def set_plan_route(tenant_id: str, plan: str = Form(...),
                         current_user: dict = Depends(_require_super)):
    from app.utils.audit import audit
    if not store.get_tenant(tenant_id):
        raise HTTPException(404, "テナントが見つかりません")
    if plan not in _PLANS:
        raise HTTPException(400, "プランが不正です")
    store.update_tenant(tenant_id, {"plan": plan})
    audit("tenant_set_plan", tenant_id=tenant_id, plan=plan, by=current_user.get("username"))
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ops/", status_code=302)
