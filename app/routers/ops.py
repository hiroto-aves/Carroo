"""運営コンソール（/ops）— 運営者(super)専用。

テナント（会社）の発行・プラン設定・シート確認。将来 Stripe 連携の管理面もここ。
一般ユーザー/会社管理者(owner)はアクセス不可（403）。
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse

from app.db import store
from app.dependencies import get_current_user
from app.ui_shell import render_page, esc
from app.utils.security import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ops", tags=["ops"])

_PLANS = ["standard", "pro"]


def _require_super(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_super"):
        raise HTTPException(403, "運営コンソールは運営者のみアクセスできます")
    return current_user


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
  </div>"""
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
