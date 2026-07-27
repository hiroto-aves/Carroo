"""Stripe 課金サービス層（テナント単位のサブスク）。

設計（docs/課金・プラン設計_ver1.0.html）:
- プラン: standard / pro。各プランに「基本料」Price と「シート」Price。
- シート quantity = 有効ユーザー数 − 1（1人目は基本料に含む）。
- 7日トライアル・カードのみ。状態の正は Webhook。

すべて env で構成し、BILLING_ENABLED / STRIPE_SECRET_KEY が無ければ無効（現行運用を壊さない）。
必要env:
  BILLING_ENABLED=on
  STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
  STRIPE_PRICE_STANDARD_BASE, STRIPE_PRICE_STANDARD_SEAT
  STRIPE_PRICE_PRO_BASE,      STRIPE_PRICE_PRO_SEAT
  APP_BASE_URL（リダイレクト先の絶対URL）
"""
import logging
import os

logger = logging.getLogger(__name__)

TRIAL_DAYS = 7


def billing_enabled() -> bool:
    return (os.getenv("BILLING_ENABLED", "off").strip().lower() in ("on", "true", "1", "yes")
            and bool(os.getenv("STRIPE_SECRET_KEY")))


def _stripe():
    """設定済みの stripe モジュールを返す（未設定/未インストールなら None）。"""
    if not billing_enabled():
        return None
    try:
        import stripe
    except Exception:
        logger.error("[Billing] stripe パッケージが未インストール")
        return None
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    return stripe


def _price_ids(plan: str) -> tuple:
    """(基本料PriceID, シートPriceID)。"""
    if plan == "pro":
        return os.getenv("STRIPE_PRICE_PRO_BASE"), os.getenv("STRIPE_PRICE_PRO_SEAT")
    return os.getenv("STRIPE_PRICE_STANDARD_BASE"), os.getenv("STRIPE_PRICE_STANDARD_SEAT")


def _base_url() -> str:
    return (os.getenv("APP_BASE_URL", "") or "").rstrip("/")


def _extra_seats(seats: int) -> int:
    """従量課金シート数 = 有効ユーザー数 − 1（1人目は基本料に含む）。最低0。"""
    return max(int(seats or 0) - 1, 0)


def get_or_create_customer(tenant: dict):
    """テナントの Stripe 顧客を取得/作成し、customer_id を返す。"""
    stripe = _stripe()
    if not stripe:
        return None
    cid = tenant.get("stripe_customer_id")
    if cid:
        return cid
    cust = stripe.Customer.create(
        name=tenant.get("name") or tenant.get("id"),
        metadata={"tenant_id": tenant.get("id")},
    )
    from app.db import store
    store.update_tenant(tenant["id"], {"stripe_customer_id": cust.id})
    return cust.id


def create_checkout_session(tenant: dict, plan: str, seats: int) -> str:
    """サブスク契約用の Stripe Checkout Session を作り、URL を返す（カードのみ・7日トライアル）。"""
    stripe = _stripe()
    if not stripe:
        raise RuntimeError("課金が有効化されていません")
    base_price, seat_price = _price_ids(plan)
    if not base_price or not seat_price:
        raise RuntimeError(f"{plan} の Price ID が未設定です")
    customer = get_or_create_customer(tenant)
    line_items = [{"price": base_price, "quantity": 1}]
    extra = _extra_seats(seats)
    if extra > 0:
        line_items.append({"price": seat_price, "quantity": extra})
    sess = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer,
        payment_method_types=["card"],
        line_items=line_items,
        subscription_data={"trial_period_days": TRIAL_DAYS,
                           "metadata": {"tenant_id": tenant["id"], "plan": plan}},
        success_url=f"{_base_url()}/billing/?ok=1",
        cancel_url=f"{_base_url()}/billing/?canceled=1",
        metadata={"tenant_id": tenant["id"], "plan": plan},
    )
    return sess.url


def create_portal_session(tenant: dict) -> str:
    """顧客ポータル（解約・カード変更）のURLを返す。"""
    stripe = _stripe()
    if not stripe:
        raise RuntimeError("課金が有効化されていません")
    cid = tenant.get("stripe_customer_id")
    if not cid:
        raise RuntimeError("顧客情報がありません（未契約）")
    ps = stripe.billing_portal.Session.create(
        customer=cid, return_url=f"{_base_url()}/billing/")
    return ps.url


def sync_seats(tenant: dict) -> None:
    """有効ユーザー数の変化をサブスクのシート数量に反映（日割り精算は Stripe 任せ）。"""
    stripe = _stripe()
    if not stripe:
        return
    sub_id = tenant.get("stripe_subscription_id")
    if not sub_id:
        return
    plan = tenant.get("plan") or "standard"
    _, seat_price = _price_ids(plan)
    extra = _extra_seats(tenant.get("seats", 0))
    try:
        sub = stripe.Subscription.retrieve(sub_id)
        seat_item = next((it for it in sub["items"]["data"]
                          if it["price"]["id"] == seat_price), None)
        if seat_item:
            stripe.SubscriptionItem.modify(seat_item["id"], quantity=extra,
                                           proration_behavior="create_prorations")
        elif extra > 0:
            stripe.SubscriptionItem.create(subscription=sub_id, price=seat_price,
                                           quantity=extra,
                                           proration_behavior="create_prorations")
        logger.info(f"[Billing] seats同期 tenant={tenant['id']} extra={extra}")
    except Exception as e:
        logger.error(f"[Billing] seats同期失敗 tenant={tenant.get('id')}: {e}")


def verify_and_parse_webhook(payload: bytes, sig_header: str):
    """Webhook 署名検証してイベントを返す（失敗時 None）。"""
    stripe = _stripe()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not stripe or not secret:
        return None
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        logger.error(f"[Billing] Webhook 署名検証失敗: {e}")
        return None


def apply_subscription_to_tenant(subscription: dict) -> None:
    """Stripe の subscription から tenant の課金状態を更新（Webhook から呼ぶ）。"""
    from app.db import store
    tenant_id = (subscription.get("metadata") or {}).get("tenant_id")
    if not tenant_id:
        # customer から辿る
        cid = subscription.get("customer")
        tenant_id = next((t["id"] for t in store.list_tenants()
                          if t.get("stripe_customer_id") == cid), None)
    if not tenant_id:
        logger.warning("[Billing] subscription に紐づくテナント不明")
        return
    plan = (subscription.get("metadata") or {}).get("plan")
    patch = {
        "stripe_subscription_id": subscription.get("id"),
        "subscription_status": subscription.get("status"),
        "current_period_end": subscription.get("current_period_end"),
    }
    if plan:
        patch["plan"] = plan
    store.update_tenant(tenant_id, patch)
    logger.info(f"[Billing] tenant={tenant_id} status={subscription.get('status')} 更新")
