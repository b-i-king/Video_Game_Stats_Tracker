"""
Subscription routes — Premium plan via Stripe.

POST /subscription/checkout   — create Stripe Checkout session (month or year)
GET  /subscription/status     — current plan + expiry for the logged-in user
POST /subscription/portal     — Stripe Customer Portal (manage / cancel)
POST /stripe_sub_webhook      — Stripe webhook: subscription lifecycle events
"""

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.core.deps import DynamicConn, CurrentUser
from api.core.database import public_pool

router = APIRouter()


class CheckoutBody(BaseModel):
    interval: str = "month"   # "month" | "year"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stripe():
    import stripe as _s
    _s.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    return _s


def _price_id(interval: str) -> str:
    pid = (
        os.getenv("STRIPE_PREMIUM_ANNUAL_PRICE_ID", "")
        if interval == "year"
        else os.getenv("STRIPE_PREMIUM_MONTHLY_PRICE_ID", "")
    )
    if not pid:
        raise HTTPException(status_code=503, detail=f"Premium {interval} price not configured.")
    return pid


def _app_url() -> str:
    return os.getenv("NEXT_PUBLIC_APP_URL", "https://yourdomain.com")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/subscription/checkout")
async def create_subscription_checkout(
    body: CheckoutBody,
    conn: DynamicConn,
    user: CurrentUser,
):
    """
    Returns {url} — redirect the user to Stripe Checkout.
    interval = 'month' | 'year'
    """
    if body.interval not in ("month", "year"):
        raise HTTPException(status_code=400, detail="interval must be 'month' or 'year'.")

    stripe   = _stripe()
    price_id = _price_id(body.interval)

    existing = await conn.fetchrow(
        "SELECT stripe_customer_id, plan FROM app.subscriptions WHERE user_id = $1",
        user["user_id"],
    )

    if existing and existing["plan"] == "premium":
        raise HTTPException(status_code=409, detail="Already subscribed to Premium.")

    customer_id = existing["stripe_customer_id"] if existing else None

    kwargs: dict = dict(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        client_reference_id=str(user["user_id"]),
        success_url=_app_url() + "/account?subscribed=1",
        cancel_url=_app_url() + "/account",
    )
    if customer_id:
        kwargs["customer"] = customer_id
    else:
        kwargs["customer_email"] = user.get("email")

    session = stripe.checkout.Session.create(**kwargs)
    return {"url": session.url}


@router.get("/subscription/status")
async def get_subscription_status(conn: DynamicConn, user: CurrentUser):
    """Return the user's current plan, billing_interval, and expiry date."""
    row = await conn.fetchrow(
        "SELECT plan, billing_interval, expires_at, cancelled_at "
        "FROM app.subscriptions WHERE user_id = $1",
        user["user_id"],
    )
    if not row or row["plan"] != "premium":
        return {"plan": "free"}

    return {
        "plan":             row["plan"],
        "billing_interval": row["billing_interval"],
        "expires_at":       row["expires_at"].isoformat() if row["expires_at"] else None,
        "cancelled":        row["cancelled_at"] is not None,
    }


@router.post("/subscription/portal")
async def create_billing_portal(conn: DynamicConn, user: CurrentUser):
    """
    Returns {url} — redirect the user to the Stripe Customer Portal
    so they can manage payment method, upgrade, or cancel.
    """
    stripe = _stripe()

    row = await conn.fetchrow(
        "SELECT stripe_customer_id FROM app.subscriptions WHERE user_id = $1",
        user["user_id"],
    )
    if not row or not row["stripe_customer_id"]:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    portal = stripe.billing_portal.Session.create(
        customer=row["stripe_customer_id"],
        return_url=_app_url() + "/account",
    )
    return {"url": portal.url}


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@router.post("/stripe_sub_webhook")
async def stripe_sub_webhook(request: Request):
    """
    Handles subscription lifecycle:
      checkout.session.completed       — new subscription, store customer_id + plan
      customer.subscription.updated    — renewal date change, cancellation flag
      customer.subscription.deleted    — subscription ended → downgrade to free
    """
    webhook_secret = os.getenv("STRIPE_SUB_WEBHOOK_SECRET", "")
    payload        = await request.body()
    sig_header     = request.headers.get("stripe-signature", "")

    if webhook_secret:
        try:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            body = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    else:
        body = json.loads(payload)

    event_type = body.get("type", "")
    obj        = body["data"]["object"]

    if public_pool is None:
        return {"status": "no_pool"}

    async with public_pool.acquire() as conn:

        # ── New subscription via Checkout ─────────────────────────────────
        if event_type == "checkout.session.completed" and obj.get("mode") == "subscription":
            user_id_str     = obj.get("client_reference_id")
            customer_id     = obj.get("customer")
            subscription_id = obj.get("subscription")

            if not user_id_str:
                return {"status": "skipped"}
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                return {"status": "skipped"}

            # Fetch sub details for interval + period_end
            import stripe as _s
            _s.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            sub      = _s.Subscription.retrieve(subscription_id)
            interval = sub["items"]["data"][0]["price"]["recurring"]["interval"]
            expires  = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

            await conn.execute("""
                INSERT INTO app.subscriptions
                    (user_id, stripe_customer_id, stripe_subscription_id,
                     plan, billing_interval, started_at, expires_at)
                VALUES ($1, $2, $3, 'premium', $4, NOW(), $5)
                ON CONFLICT (user_id) DO UPDATE
                    SET stripe_customer_id     = EXCLUDED.stripe_customer_id,
                        stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                        plan                   = 'premium',
                        billing_interval       = EXCLUDED.billing_interval,
                        started_at             = NOW(),
                        expires_at             = EXCLUDED.expires_at,
                        cancelled_at           = NULL
            """, user_id, customer_id, subscription_id, interval, expires)

        # ── Subscription updated (renewal, plan change, cancel scheduled) ─
        elif event_type == "customer.subscription.updated":
            subscription_id = obj["id"]
            interval  = obj["items"]["data"][0]["price"]["recurring"]["interval"]
            expires   = datetime.fromtimestamp(obj["current_period_end"], tz=timezone.utc)
            status    = obj.get("status", "")
            plan      = "premium" if status in ("active", "trialing") else "free"
            cancel_at = obj.get("cancel_at")
            cancelled_at = (
                datetime.fromtimestamp(cancel_at, tz=timezone.utc) if cancel_at else None
            )

            await conn.execute("""
                UPDATE app.subscriptions
                SET plan             = $1,
                    billing_interval = $2,
                    expires_at       = $3,
                    cancelled_at     = $4
                WHERE stripe_subscription_id = $5
            """, plan, interval, expires, cancelled_at, subscription_id)

        # ── Subscription deleted (hard cancel / non-payment) ──────────────
        elif event_type == "customer.subscription.deleted":
            subscription_id = obj["id"]
            await conn.execute("""
                UPDATE app.subscriptions
                SET plan         = 'free',
                    cancelled_at = NOW()
                WHERE stripe_subscription_id = $1
            """, subscription_id)

    return {"status": "ok"}
