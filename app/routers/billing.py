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


def _base_per(plan: str):
    return (5000, 3000) if plan == "pro" else (4000, 2000)


@router.get("/", response_class=HTMLResponse)
async def billing_home(current_user: dict = Depends(_require_owner)):
    tid = current_tenant_id(current_user)
    tenant = store.get_tenant(tid) or {}
    tenant.setdefault("id", tid)
    on = billing.billing_enabled()
    # 契約中なら Stripe の最新状態を取り込み（seat_limit 等を自己修復）
    if on and tenant.get("stripe_subscription_id"):
        tenant = billing.refresh_tenant(tenant)

    plan = tenant.get("plan") or "standard"
    status = tenant.get("subscription_status")
    used = store.count_tenant_users(tid)                 # 使用中（在籍ユーザー数）
    active = status in ("active", "trialing", "past_due")
    seat_limit = tenant.get("seat_limit") if tenant.get("seat_limit") is not None else (used if not active else used)
    base, per = _base_per(plan)
    est = base + per * max(int(seat_limit or 1) - 1, 0)

    status_chip = {
        "active": '<span class="chip live">有効</span>',
        "trialing": '<span class="chip live">トライアル中</span>',
        "past_due": '<span class="chip wait">支払い遅延</span>',
        "canceled": '<span class="chip off">解約済み</span>',
    }.get(status, '<span class="chip off">未契約</span>')

    notice = ""
    if not on:
        notice = ('<div style="background:var(--amber-wash);border:1px solid var(--amber);'
                  'color:var(--amber);border-radius:12px;padding:12px 15px;margin-bottom:16px;font-size:13px">'
                  '課金は現在テスト準備中です（未有効化）。参考表示です。</div>')

    # 契約 or シート変更フォーム
    min_seats = max(used, 1)
    if not on:
        action = ""
    elif active:
        # シート数変更（買い増し/減）＋ 支払い管理
        action = (
          f'<form method="post" action="/billing/seats" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px">'
          f'<div><label class="fl">契約シート数（課金対象の人数）</label>'
          f'<input type="number" name="seats" value="{int(seat_limit or min_seats)}" min="{min_seats}" max="200" style="width:120px"></div>'
          f'<button class="btn" type="submit">シート数を変更</button></form>'
          f'<p class="hl" style="font-size:12px;margin:0 0 14px">※ 使用中 {used} 人より少なくはできません。減らす場合は先にユーザーを削除してください。</p>'
          '<form method="post" action="/billing/portal"><button class="btn ghost" type="submit">お支払い・カードの管理／解約</button></form>')
    else:
        action = (
          '<form method="post" action="/billing/checkout" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap">'
          '<div><label class="fl">プラン</label><select name="plan" style="width:auto">'
          f'<option value="standard"{" selected" if plan=="standard" else ""}>Standard（¥4,000＋¥2,000/人）</option>'
          f'<option value="pro"{" selected" if plan=="pro" else ""}>Pro（¥5,000＋¥3,000/人）</option></select></div>'
          f'<div><label class="fl">契約シート数</label><input type="number" name="seats" value="{min_seats}" min="{min_seats}" max="200" style="width:120px"></div>'
          '<button class="btn" type="submit">契約する（7日間無料）</button></form>'
          f'<p class="hl" style="font-size:12px;margin:10px 0 0">まず利用人数分のシートを契約し、その枠内でユーザーを発行します。追加したくなったらここでシートを増やせます。</p>')

    body = f"""
  <h1 class="pt">お支払い・プラン</h1>
  <p class="hl" style="margin:0 0 16px">会社単位のご契約。<b>契約シート数の枠内でユーザーを発行</b>できます（1人目は基本料に含む）。</p>
  {notice}
  <div class="card" style="padding:22px;max-width:660px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
      <div style="font-size:18px;font-weight:700">{esc(_PLAN_JA.get(plan, plan))}</div>{status_chip}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:13.5px;margin-bottom:20px">
      <div><span class="hl">契約シート</span><div style="font-weight:600">{int(seat_limit or min_seats)} 人</div></div>
      <div><span class="hl">使用中</span><div style="font-weight:600">{used} 人</div></div>
      <div><span class="hl">月額</span><div style="font-weight:600">¥{est:,} / 月</div></div>
    </div>
    {action}
  </div>
  <p style="margin:16px 2px 0;font-size:12px;color:var(--faint)">
    <a href="/legal/tokushoho" style="color:var(--faint)">特定商取引法に基づく表記</a> ·
    <a href="/legal/terms" style="color:var(--faint)">利用規約</a> ·
    <a href="/legal/privacy" style="color:var(--faint)">プライバシーポリシー</a></p>"""
    return HTMLResponse(render_page(title="お支払い・プラン", active="billing",
                                    body=body, user=current_user, crumb="Carroo · 課金"))


@router.post("/checkout")
async def checkout(plan: str = Form("standard"), seats: int = Form(1),
                   current_user: dict = Depends(_require_owner)):
    if not billing.billing_enabled():
        raise HTTPException(400, "課金は現在有効化されていません")
    tid = current_tenant_id(current_user)
    tenant = store.get_tenant(tid) or {}
    tenant.setdefault("id", tid)
    used = store.count_tenant_users(tid)
    seat_limit = max(int(seats or 1), used, 1)   # 使用中人数を下回れない
    try:
        url = billing.create_checkout_session(
            tenant, plan if plan in ("standard", "pro") else "standard", seat_limit)
    except Exception as e:
        raise HTTPException(400, f"決済ページの作成に失敗しました: {e}")
    return RedirectResponse(url=url, status_code=303)


@router.post("/seats", response_class=HTMLResponse)
async def change_seats_confirm(seats: int = Form(...),
                               current_user: dict = Depends(_require_owner)):
    """シート数変更の【最終確認画面】。ここでは課金しない（特商法の確認導線）。"""
    if not billing.billing_enabled():
        raise HTTPException(400, "課金は現在有効化されていません")
    tid = current_tenant_id(current_user)
    tenant = store.get_tenant(tid) or {}
    used = store.count_tenant_users(tid)
    want = int(seats or 1)
    if want < used:
        raise HTTPException(400, f"使用中の {used} 人より少なくはできません。先にユーザーを削除してください。")
    want = max(want, 1)
    plan = tenant.get("plan") or "standard"
    cur = int(tenant.get("seat_limit") or used or 1)
    base, per = _base_per(plan)
    cur_amt = base + per * max(cur - 1, 0)
    new_amt = base + per * max(want - 1, 0)
    diff = new_amt - cur_amt
    up = diff >= 0
    diff_txt = (f'増額 <b style="color:#C9503E">+¥{diff:,}</b>' if diff > 0
                else (f'減額 <b>−¥{-diff:,}</b>' if diff < 0 else '変更なし'))
    proration = ('今回の変更ぶんは<b>日割りで計算</b>され、次回以降のご請求に反映されます。'
                 if up else '減額ぶんは次回以降のご請求に反映されます（日割りクレジット）。')
    body = f"""
  <h1 class="pt">契約内容の変更 確認</h1>
  <p class="hl" style="margin:0 0 16px">下記の内容で契約シート数を変更します。ご確認のうえ「この内容で変更する」を押してください。</p>
  <div class="card" style="padding:22px;max-width:560px">
    <table style="width:100%;font-size:14px">
      <tr><td class="hl" style="padding:6px 0">プラン</td><td style="text-align:right;font-weight:600">{esc(_PLAN_JA.get(plan, plan))}</td></tr>
      <tr><td class="hl" style="padding:6px 0">契約シート数</td><td style="text-align:right;font-weight:600">{cur} 人 → <b style="color:var(--signal-ink)">{want} 人</b></td></tr>
      <tr><td class="hl" style="padding:6px 0">月額（税別）</td><td style="text-align:right;font-weight:600">¥{cur_amt:,} → <b>¥{new_amt:,}</b> / 月</td></tr>
      <tr><td class="hl" style="padding:6px 0">差額</td><td style="text-align:right">{diff_txt}</td></tr>
    </table>
    <div style="background:var(--raise);border:1px solid var(--line-soft);border-radius:10px;padding:12px 14px;margin:14px 0;font-size:12.5px;color:var(--muted);line-height:1.7">
      ・支払方法：登録済みのクレジットカード<br>
      ・支払時期：{proration}<br>
      ・以後、毎月自動で継続課金されます（金額は上記「変更後」）。<br>
      ・解約・カード変更は「お支払い管理」からいつでも可能です。
    </div>
    <form method="post" action="/billing/seats/confirm" style="display:flex;gap:10px">
      <input type="hidden" name="seats" value="{want}">
      <button class="btn" type="submit">この内容で変更する</button>
      <a class="btn ghost" href="/billing/">キャンセル</a>
    </form>
  </div>"""
    return HTMLResponse(render_page(title="契約変更の確認", active="billing",
                                    body=body, user=current_user, crumb="Carroo · 課金"))


@router.post("/seats/confirm")
async def change_seats_apply(seats: int = Form(...),
                             current_user: dict = Depends(_require_owner)):
    """確認後にシート数を実際に変更（ここで初めて課金内容が変わる）。"""
    if not billing.billing_enabled():
        raise HTTPException(400, "課金は現在有効化されていません")
    tid = current_tenant_id(current_user)
    tenant = store.get_tenant(tid) or {}
    tenant.setdefault("id", tid)
    used = store.count_tenant_users(tid)
    want = max(int(seats or 1), 1)
    if want < used:
        raise HTTPException(400, f"使用中の {used} 人より少なくはできません。")
    try:
        billing.set_subscription_seats(tenant, want)
    except Exception as e:
        raise HTTPException(400, f"シート数の変更に失敗しました: {e}")
    from app.utils.audit import audit
    audit("seats_change", tenant_id=tid, seats=want, by=current_user.get("username"))
    return RedirectResponse(url="/billing/?seats_changed=1", status_code=303)


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
