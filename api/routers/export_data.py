"""
Data export routes.

GET  /export/row_count   — user's stat row count + computed price tier + upgrade info
GET  /export/download    — streams CSV or JSON (owner free; others need power_pack purchase)
POST /export/checkout    — create Stripe Checkout (new purchase or tier upgrade)
POST /stripe_webhook     — Stripe webhook; records purchase / updates tier ceiling
"""

import csv
import io
import json
import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.core.deps import DynamicConn, CurrentUser
from api.core.database import public_pool

router = APIRouter()


# ---------------------------------------------------------------------------
# Tier helpers
# ---------------------------------------------------------------------------

def _price_for_rows(row_count: int) -> float:
    if row_count < 500:     return 1.00
    if row_count < 2_001:   return 2.00
    if row_count < 10_001:  return 4.00
    return 6.00

def _tier_ceiling(row_count: int) -> int:
    """Upper bound of the tier the user is currently in."""
    if row_count < 500:     return 499
    if row_count < 2_001:   return 2_000
    if row_count < 10_001:  return 10_000
    return 999_999_999

def _tier_label(row_count: int) -> str:
    if row_count < 500:     return "< 500 rows"
    if row_count < 2_001:   return "500–2,000 rows"
    if row_count < 10_001:  return "2,001–10,000 rows"
    return "10,000+ rows"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/export/row_count")
async def get_row_count(conn: DynamicConn, user: CurrentUser):
    uid = user["user_id"]

    row_count = await conn.fetchval("""
        SELECT COUNT(*)
        FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        WHERE p.user_id = $1
    """, uid)
    row_count = int(row_count or 0)

    purchase = await conn.fetchrow("""
        SELECT amount_cents, tier_ceiling_rows
        FROM app.power_pack_purchases WHERE user_id = $1
    """, uid)

    is_owner      = user.get("is_owner", False)
    current_price = _price_for_rows(row_count)

    if is_owner:
        return {
            "row_count":     row_count,
            "price":         current_price,
            "tier_label":    _tier_label(row_count),
            "purchased":     True,
            "needs_upgrade": False,
            "upgrade_price": None,
        }

    if not purchase:
        return {
            "row_count":     row_count,
            "price":         current_price,
            "tier_label":    _tier_label(row_count),
            "purchased":     False,
            "needs_upgrade": False,
            "upgrade_price": None,
        }

    # Has purchased — check if they've grown past their tier ceiling
    paid_ceiling  = purchase["tier_ceiling_rows"]
    paid_cents    = purchase["amount_cents"]
    needs_upgrade = row_count > paid_ceiling

    upgrade_price = None
    if needs_upgrade:
        current_cents = int(current_price * 100)
        diff_cents    = max(current_cents - paid_cents, 0)
        upgrade_price = round(diff_cents / 100, 2)

    return {
        "row_count":     row_count,
        "price":         current_price,
        "tier_label":    _tier_label(row_count),
        "purchased":     not needs_upgrade,   # treat as unpurchased if upgrade needed
        "needs_upgrade": needs_upgrade,
        "upgrade_price": upgrade_price,
    }


@router.get("/export/download")
async def download_export(
    conn:   DynamicConn,
    user:   CurrentUser,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
):
    is_owner = user.get("is_owner", False)
    uid      = user["user_id"]

    if not is_owner:
        purchase = await conn.fetchrow("""
            SELECT tier_ceiling_rows FROM app.power_pack_purchases WHERE user_id = $1
        """, uid)

        if not purchase:
            raise HTTPException(status_code=402, detail="Power Pack purchase required.")

        # Enforce tier ceiling
        row_count = await conn.fetchval("""
            SELECT COUNT(*) FROM fact.fact_game_stats f
            JOIN dim.dim_players p ON f.player_id = p.player_id
            WHERE p.user_id = $1
        """, uid)
        if int(row_count or 0) > purchase["tier_ceiling_rows"]:
            raise HTTPException(
                status_code=402,
                detail="Your data has grown past your purchased tier. Please upgrade to download."
            )

    rows = await conn.fetch("""
        SELECT
            p.player_name,
            g.game_name,
            g.game_installment,
            f.game_mode,
            f.stat_type,
            f.stat_value,
            f.win,
            f.notes,
            f.played_at
        FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        JOIN dim.dim_games   g ON f.game_id   = g.game_id
        WHERE p.user_id = $1
        ORDER BY f.played_at DESC
    """, uid)

    if format == "json":
        data = [dict(r) for r in rows]
        for row in data:
            if row.get("played_at"):
                row["played_at"] = row["played_at"].isoformat()
            if row.get("win") is not None:
                row["win_loss"] = "Win" if row["win"] == 1 else "Loss"
            row.pop("win", None)
        content  = json.dumps(data, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="game_stats_export.json"'},
        )

    fieldnames = [
        "player_name", "game_name", "game_installment", "game_mode",
        "stat_type", "stat_value", "win_loss", "notes", "played_at",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        row = dict(r)
        if row.get("played_at"):
            row["played_at"] = row["played_at"].isoformat()
        win = row.pop("win", None)
        row["win_loss"] = "Win" if win == 1 else ("Loss" if win == 0 else "")
        writer.writerow(row)

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="game_stats_export.csv"'},
    )


@router.post("/export/checkout")
async def create_export_checkout(conn: DynamicConn, user: CurrentUser):
    """
    Create a Stripe Checkout session using dynamic price_data (one product, no pre-set prices).
    Handles both new purchases and tier upgrades — upgrade charges only the difference.
    """
    import stripe

    product_id = os.getenv("STRIPE_POWER_PACK_PRODUCT_ID", "")
    if not product_id:
        raise HTTPException(status_code=503, detail="Power Pack checkout is not configured.")

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    app_url        = os.getenv("NEXT_PUBLIC_APP_URL", "https://yourdomain.com")

    row_count = int((await conn.fetchval("""
        SELECT COUNT(*) FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        WHERE p.user_id = $1
    """, user["user_id"])) or 0)

    current_price_cents = int(_price_for_rows(row_count) * 100)
    ceiling             = _tier_ceiling(row_count)

    purchase = await conn.fetchrow("""
        SELECT amount_cents, tier_ceiling_rows
        FROM app.power_pack_purchases WHERE user_id = $1
    """, user["user_id"])

    if purchase and row_count <= purchase["tier_ceiling_rows"]:
        raise HTTPException(status_code=409, detail="Power Pack already covers your current data.")

    # Upgrade: charge only the difference; new purchase: charge full price
    if purchase:
        charge_cents = max(current_price_cents - purchase["amount_cents"], 0)
        description  = f"Power Pack upgrade — now covers up to {ceiling:,} rows"
    else:
        charge_cents = current_price_cents
        description  = f"Power Pack — export up to {ceiling:,} rows (CSV & JSON)"

    if charge_cents == 0:
        raise HTTPException(status_code=409, detail="No additional charge needed for this tier.")

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency":    "usd",
                "unit_amount": charge_cents,
                "product":     product_id,
            },
            "quantity": 1,
        }],
        client_reference_id=str(user["user_id"]),
        customer_email=user.get("email"),
        success_url=app_url + "/data-export?purchased=1",
        cancel_url=app_url + "/data-export",
        metadata={"tier_ceiling_rows": str(ceiling), "is_upgrade": str(purchase is not None)},
    )
    return {"url": session.url}


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@router.post("/stripe_webhook")
async def stripe_webhook(request: Request):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    payload        = await request.body()
    sig_header     = request.headers.get("stripe-signature", "")

    if webhook_secret:
        try:
            import stripe
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")

    body       = json.loads(payload)
    event_type = body.get("type", "")

    if event_type == "checkout.session.completed":
        session      = body["data"]["object"]
        user_id_str  = session.get("client_reference_id")
        amount_total = session.get("amount_total", 0)
        metadata     = session.get("metadata", {})

        if not user_id_str:
            return {"status": "skipped", "reason": "no user_id"}
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            return {"status": "skipped", "reason": "invalid user_id"}

        tier_ceiling = int(metadata.get("tier_ceiling_rows", 499))
        is_upgrade   = metadata.get("is_upgrade") == "True"

        async with public_pool.acquire() as conn:
            if is_upgrade:
                # Upgrade: add the charge to cumulative amount_cents, update ceiling
                await conn.execute("""
                    UPDATE app.power_pack_purchases
                    SET amount_cents      = amount_cents + $1,
                        tier_ceiling_rows = $2,
                        stripe_session_id = $3
                    WHERE user_id = $4
                """, amount_total, tier_ceiling, session.get("id"), user_id)
            else:
                await conn.execute("""
                    INSERT INTO app.power_pack_purchases
                        (user_id, amount_cents, tier_ceiling_rows, stripe_session_id)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id) DO NOTHING
                """, user_id, amount_total, tier_ceiling, session.get("id"))

    return {"status": "ok"}
