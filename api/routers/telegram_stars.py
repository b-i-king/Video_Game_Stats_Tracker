"""
Telegram Stars payment — invoice creation.

POST /telegram_stars/invoice
  Creates a Telegram Stars invoice link for the Premium monthly subscription
  and returns it to the Mini App. The Mini App calls
  window.Telegram.WebApp.openInvoice(link, callback) to show the payment sheet.

Stars price: 750 XTR (~$9.75 developer payout at $0.013/star)

Env vars:
  TELEGRAM_BROADCAST_BOT_TOKEN  — used for all Telegram Bot API calls
  TELEGRAM_STARS_PRICE          — override default 750 (integer Stars)
"""

import os
import requests

from fastapi import APIRouter, HTTPException

from api.core.deps import DynamicConn, CurrentUser

router = APIRouter()

_STARS_PRICE = int(os.getenv("TELEGRAM_STARS_PRICE", "750"))


def _bot_token() -> str:
    t = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
    if not t:
        raise HTTPException(status_code=503, detail="Telegram bot not configured.")
    return t


@router.post("/telegram_stars/invoice")
async def create_stars_invoice(conn: DynamicConn, user: CurrentUser):
    """
    Create a Telegram Stars invoice link scoped to the authenticated user.
    The invoice payload encodes the user_id so the webhook knows who to upgrade.
    """
    user_id  = user["user_id"]
    is_owner = user.get("is_owner", False)

    # Verify the user is logged in via Telegram (has a telegram_user_id).
    # Owners are exempt — their JWT was issued by telegram_auth.py which already
    # verified their Telegram identity. The personal DB has no telegram_user_id column.
    if not is_owner:
        tg_id = await conn.fetchval(
            "SELECT telegram_user_id FROM dim.dim_users WHERE user_id = $1", user_id
        )
        if not tg_id:
            raise HTTPException(
                status_code=400,
                detail="No Telegram account linked. Open the app inside Telegram to pay with Stars.",
            )

    token   = _bot_token()
    payload = f"premium_monthly_{user_id}"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/createInvoiceLink",
            json={
                "title":       "Premium — 1 Month",
                "description": "Full access: 5 player profiles, leaderboard, AI insights, data export.",
                "payload":     payload,
                "currency":    "XTR",                       # Telegram Stars
                "prices":      [{"label": "Premium Monthly", "amount": _STARS_PRICE}],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Telegram API error: {exc}")

    if not data.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram API: {data.get('description')}")

    return {"invoice_link": data["result"]}
