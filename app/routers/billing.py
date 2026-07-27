"""課金（Stripe）ルーター。

- GET  /billing/          : 会社管理者(owner)向け 契約状況＋契約/管理ボタン
- POST /billing/checkout  : Checkout セッション作成→Stripe へリダイレクト
- POST /billing/portal    : 顧客ポータルへリダイレクト（解約・カード変更）
- POST /billing/webhook   : Stripe Webhook（署名検証・状態同期）※認証不要
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.db import store
from app.dependencies import get_current_user
from app.services import billing
from app.tenancy import current_tenant_id
from app.ui_shell import render_page, esc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

_STATUS_JA = {
    "trialing": "トライアル中", "active": "有効", "past_due": "支払い遅延",
    "canceled": "解約済み", "unpaid": "未払い", "incomplete": "手続き未完了", None: "未契約",
}
_PLAN_JA = {"standard": "Standard（¥4,000＋¥2,000/人）", "pro": "Pro（¥5,000＋¥3,000/人）"}


def _require_owner(current_user: dict = Depends(get_current_user)) -> dict:
    # 会社管理者(owner) か 運営者(super) のみ課金操作可
    if not (current_user.get("role") == "owner" or current_user.get("is_super")):
        raise HTTPException(403, "課金の操作は会社管理者のみ可能です")
    return current_user


@router.get("/", response_class=HTMLResponse)
async def billing_home(current_user: dict = Depends(_require_owner)):
    tenant = store.get_tenant(current_tenant_id(current_user)) or {}
    plan = tenant.get("plan") or "standard"
    status = tenant.get("subscription_status")
    seats = tenant.get("seats", 0)
    extra = max(int(seats or 0) - 1, 0)
    on = billing.billing_enabled()

    def _amt(p):
        base, per = (5000, 3000) if p == "pro" else (4000, 2000)
        return base + per * extra
    est = _amt(plan)

    status_chip = {
        "active": '<span class="chip live">有効</span>',
        "trialing": '<span class="chip live">トライアル中</span>',
        "past_due": '<span class="chip wait">支払い遅延</span>',
        "canceled": '<span class="chip off">解約済み</span>',
    }.get(status, '<span class="chip off">未契約</span>')

    if not on:
        notice = ('<div style="background:var(--amber-wash);border:1px solid var(--amber);'
                  'color:var(--amber);border-radius:12px;padding:12px 15px;margin-bottom:16px;font-size:13px">'
                  '課金は現在テスト準備中です（未有効化）。この画面の内容は参考表示です。</div>')
        action = ""
    else:
        notice = ""
        if status in ("active", "trialing", "past_due"):
            action = ('<form method="post" action="/billing/portal">'
                      '<button class="btn" type="submit">お支払い・プランの管理</button></form>')
        else:
            action = (
              '<form method="post" action="/billing/checkout" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">'
              '<div><label class="fl">プラン</label>'
              '<select name="plan" style="width:auto">'
              f'<option value="standard"{" selected" if plan=="standard" else ""}>Standard</option>'
              f'<option value="pro"{" selected" if plan=="pro" else ""}>Pro</option></select></div>'
              '<button class="btn" type="submit">契約する（7日間無料）</button></form>')

    body = f"""
  <h1 class="pt">お支払い・プラン</h1>
  <p class="hl" style="margin:0 0 16px">会社（テナント）単位のご契約です。1人目は基本料に含み、2人目以降が従量課金。</p>
  {notice}
  <div class="card" style="padding:22px;max-width:640px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
      <div style="font-size:18px;font-weight:700">{esc(_PLAN_JA.get(plan, plan))}</div>{status_chip}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:13.5px;margin-bottom:18px">
      <div><span class="hl">ユーザー数</span><div style="font-weight:600">{seats} 人（従量 {extra} 人分）</div></div>
      <div><span class="hl">今月の目安</span><div style="font-weight:600">¥{est:,} / 月</div></div>
      <div><span class="hl">状態</span><div style="font-weight:600">{esc(_STATUS_JA.get(status, status or '未契約'))}</div></div>
    </div>
    {action}
  </div>"""
    return HTMLResponse(render_page(title="お支払い・プラン", active="billing",
                                    body=body, user=current_user, crumb="Carroo · 課金"))


@router.post("/checkout")
async def checkout(plan: str = Form("standard"),
                   current_user: dict = Depends(_require_owner)):
    if not billing.billing_enabled():
        raise HTTPException(400, "課金は現在有効化されていません")
    tenant = store.get_tenant(current_tenant_id(current_user)) or {}
    tenant.setdefault("id", current_tenant_id(current_user))
    try:
        url = billing.create_checkout_session(tenant, plan if plan in ("standard", "pro") else "standard",
                                              tenant.get("seats", 0))
    except Exception as e:
        raise HTTPException(400, f"決済ページの作成に失敗しました: {e}")
    return RedirectResponse(url=url, status_code=303)


@router.post("/portal")
async def portal(current_user: dict = Depends(_require_owner)):
    if not billing.billing_enabled():
        raise HTTPException(400, "課金は現在有効化されていません")
    tenant = store.get_tenant(current_tenant_id(current_user)) or {}
    try:
        url = billing.create_portal_session(tenant)
    except Exception as e:
        raise HTTPException(400, f"管理ページの作成に失敗しました: {e}")
    return RedirectResponse(url=url, status_code=303)


@router.post("/webhook")
async def webhook(request: Request):
    """Stripe Webhook。署名検証し、subscription 系イベントで tenant を同期。"""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = billing.verify_and_parse_webhook(payload, sig)
    if event is None:
        raise HTTPException(400, "invalid webhook")
    etype = event["type"]
    obj = event["data"]["object"]
    try:
        if etype in ("customer.subscription.created", "customer.subscription.updated",
                     "customer.subscription.deleted", "customer.subscription.trial_will_end"):
            billing.apply_subscription_to_tenant(obj)
        elif etype == "checkout.session.completed" and obj.get("subscription"):
            import stripe
            sub = stripe.Subscription.retrieve(obj["subscription"])
            billing.apply_subscription_to_tenant(sub)
    except Exception as e:
        logger.error(f"[Billing] webhook {etype} 処理失敗: {e}")
    return JSONResponse({"received": True})
