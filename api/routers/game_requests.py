"""
Game request routes — Public pool.

Public users submit game requests; owner approves/rejects via Telegram inline
buttons or directly via the API. Approved requests are auto-synced to the
public dim.dim_games catalog via the admin.sync_game_to_public logic.

Endpoints:
  POST /game_requests              — any authenticated user submits a request
  GET  /game_requests              — owner sees all; users see their own
  PATCH /game_requests/{id}/approve — owner approves → syncs to public catalog
  PATCH /game_requests/{id}/reject  — owner rejects with optional reason
  POST /telegram_webhook           — Telegram callback for inline button taps
"""

import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

from api.core.deps import DynamicConn, CurrentUser, OwnerUser
from api.core.database import public_pool
from utils.telegram_utils import notifier

router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class GameRequestBody(BaseModel):
    game_name:        str
    game_installment: str | None = None
    game_genre:       str | None = None
    game_subgenre:    str | None = None


class RejectBody(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helper — shared approve logic (used by PATCH and Telegram webhook)
# ---------------------------------------------------------------------------

async def _resolve_owner_id(conn) -> int | None:
    """Look up the owner's user_id from the OWNER_EMAIL env var."""
    owner_email = os.getenv("OWNER_EMAIL", "").lower().strip()
    if not owner_email:
        return None
    return await conn.fetchval(
        "SELECT user_id FROM dim.dim_users WHERE user_email = $1", owner_email
    )


async def _do_approve(request_id: int, approved_by_id: int | None, approved_by_email: str = "") -> dict:
    """Approve a request and sync the game to the public catalog."""
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not available.")

    async with public_pool.acquire() as conn:
        if approved_by_id is None:
            approved_by_id = await _resolve_owner_id(conn)

        row = await conn.fetchrow("""
            SELECT * FROM app.game_requests WHERE request_id = $1
        """, request_id)

        if not row:
            raise HTTPException(status_code=404, detail="Request not found.")
        if row["status"] != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Request is already '{row['status']}'.",
            )

        await conn.execute("""
            UPDATE app.game_requests
            SET status = 'approved', reviewed_by = $1, reviewed_at = NOW()
            WHERE request_id = $2
        """, approved_by_id, request_id)

    # Sync to public catalog — reuse admin logic directly
    from api.routers.admin import SyncGameRequest, sync_game_to_public as _sync

    class _FakeOwner(dict):
        pass

    fake_user = _FakeOwner({"email": approved_by, "is_owner": True, "role": "owner"})

    sync_body = SyncGameRequest(
        game_name=row["game_name"],
        game_installment=row["game_installment"],
        game_genre=row["game_genre"],
        game_subgenre=row["game_subgenre"],
    )

    try:
        result = await _sync(sync_body, fake_user)
    except HTTPException as e:
        # Game not in personal catalog yet — log and continue (owner can sync manually)
        print(f"[game_requests] Approve sync warning: {e.detail}")
        result = {"status": "sync_pending", "message": e.detail}

    label = approved_by_email or f"user_id={approved_by_id}"
    print(f"[game_requests] Request #{request_id} approved by {label}")
    return result


async def _do_reject(request_id: int, rejected_by_id: int | None, reason: str | None, rejected_by_email: str = "") -> None:
    """Mark a request as rejected."""
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not available.")

    async with public_pool.acquire() as conn:
        if rejected_by_id is None:
            rejected_by_id = await _resolve_owner_id(conn)

        row = await conn.fetchrow(
            "SELECT status FROM app.game_requests WHERE request_id = $1", request_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Request not found.")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail=f"Request is already '{row['status']}'.")

        await conn.execute("""
            UPDATE app.game_requests
            SET status = 'rejected', reviewed_by = $1, reviewed_at = NOW(),
                rejection_reason = $2
            WHERE request_id = $3
        """, rejected_by_id, reason, request_id)

    label = rejected_by_email or f"user_id={rejected_by_id}"
    print(f"[game_requests] Request #{request_id} rejected by {label} — reason: {reason}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/game_requests", status_code=201)
async def submit_game_request(
    body: GameRequestBody,
    conn: DynamicConn,
    user: CurrentUser,
):
    """
    Submit a game request to the public catalog.
    Any authenticated user may request a game. Duplicates (same name + installment
    already in dim.dim_games or already pending) are rejected.
    """
    if not body.game_name.strip():
        raise HTTPException(status_code=400, detail="game_name is required.")

    # Check if game already exists in public catalog
    existing_game = await conn.fetchval("""
        SELECT game_id FROM dim.dim_games
        WHERE LOWER(game_name) = LOWER($1)
          AND (
              game_installment IS NULL AND $2::TEXT IS NULL
              OR LOWER(game_installment) = LOWER($2)
          )
    """, body.game_name, body.game_installment)

    if existing_game:
        raise HTTPException(
            status_code=409,
            detail="This game is already in the catalog.",
        )

    # Check for duplicate pending request
    existing_request = await conn.fetchval("""
        SELECT request_id FROM app.game_requests
        WHERE LOWER(game_name) = LOWER($1)
          AND (
              game_installment IS NULL AND $2::TEXT IS NULL
              OR LOWER(game_installment) = LOWER($2)
          )
          AND status = 'pending'
    """, body.game_name, body.game_installment)

    if existing_request:
        raise HTTPException(
            status_code=409,
            detail="A pending request for this game already exists.",
        )

    request_id = await conn.fetchval("""
        INSERT INTO app.game_requests
            (user_id, game_name, game_installment, game_genre, game_subgenre)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING request_id
    """, user["user_id"], body.game_name.strip(), body.game_installment,
         body.game_genre, body.game_subgenre)

    # Notify owner via Telegram
    notifier.send_game_request(
        request_id=request_id,
        user_email=user["email"],
        game_name=body.game_name,
        game_installment=body.game_installment,
        game_genre=body.game_genre,
        game_subgenre=body.game_subgenre,
        approve_url="",  # inline buttons handle this — no URL needed
    )

    return {
        "request_id": request_id,
        "status":     "pending",
        "message":    "Your game request has been submitted. You'll be notified when it's reviewed.",
    }


@router.get("/game_requests")
async def list_game_requests(conn: DynamicConn, user: CurrentUser):
    """
    Owner sees all requests ordered by created_at desc.
    Other users see only their own requests.
    """
    is_owner = user.get("is_owner", False)

    if is_owner:
        rows = await conn.fetch("""
            SELECT gr.request_id, u.user_email, gr.game_name, gr.game_installment,
                   gr.game_genre, gr.game_subgenre, gr.status, gr.reviewed_by,
                   gr.rejection_reason, gr.created_at, gr.reviewed_at
            FROM app.game_requests gr
            JOIN dim.dim_users u ON u.user_id = gr.user_id
            ORDER BY
                CASE gr.status WHEN 'pending' THEN 0 ELSE 1 END,
                gr.created_at DESC
        """)
    else:
        rows = await conn.fetch("""
            SELECT request_id, game_name, game_installment, game_genre,
                   game_subgenre, status, rejection_reason, created_at, reviewed_at
            FROM app.game_requests
            WHERE user_id = $1
            ORDER BY created_at DESC
        """, user["user_id"])

    return {"requests": [dict(r) for r in rows]}


@router.patch("/game_requests/{request_id}/approve", status_code=200)
async def approve_game_request(request_id: int, user: OwnerUser):
    """Approve a pending request and sync the game to the public catalog."""
    result = await _do_approve(request_id, user["user_id"], user["email"])
    return {"status": "approved", "sync": result}


@router.patch("/game_requests/{request_id}/reject", status_code=200)
async def reject_game_request(
    request_id: int,
    body:       RejectBody,
    user:       OwnerUser,
):
    """Reject a pending request with an optional reason."""
    await _do_reject(request_id, user["user_id"], body.reason, user["email"])
    return {"status": "rejected"}


# ---------------------------------------------------------------------------
# Telegram webhook — handles inline button callback_queries
# ---------------------------------------------------------------------------

def _verify_telegram_token(request_token: str | None) -> bool:
    """Verify the request comes from our bot using the token hash."""
    bot_token = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN", "")
    if not bot_token or not request_token:
        return False
    # Telegram sends the bot token in X-Telegram-Bot-Api-Secret-Token header
    # when you set a secret_token on setWebhook. We use a simple HMAC of the token.
    expected = hmac.new(
        bot_token.encode(),
        bot_token.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, request_token)


@router.post("/telegram_webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """
    Receives callback_query events from Telegram inline buttons.
    Called when owner taps ✅ Approve or ❌ Reject on a game request notification.

    Security: Telegram sends X-Telegram-Bot-Api-Secret-Token header (set during
    webhook registration). We verify it matches a hash of our bot token.
    """
    if not _verify_telegram_token(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    callback = body.get("callback_query")
    if not callback:
        # Not a callback — could be a regular message, just ack
        return {"ok": True}

    callback_id   = callback["id"]
    chat_id       = callback["message"]["chat"]["id"]
    message_id    = callback["message"]["message_id"]
    data          = callback.get("data", "")
    from_username = callback["from"].get("username", "owner")

    owner_email = os.getenv("OWNER_EMAIL", "")

    try:
        action, req_id_str = data.split(":", 1)
        request_id = int(req_id_str)
    except (ValueError, AttributeError):
        notifier.answer_callback(callback_id, "Invalid action.")
        return {"ok": True}

    if action == "approve":
        try:
            # Pass None for user_id — _do_approve will look it up from OWNER_EMAIL
            await _do_approve(request_id, None, owner_email)
            notifier.answer_callback(callback_id, "✅ Approved!")
            notifier.edit_message_reply_markup(
                chat_id, message_id,
                f"✅ <b>Request #{request_id} approved</b> by @{from_username}",
            )
        except HTTPException as e:
            notifier.answer_callback(callback_id, f"Error: {e.detail}")

    elif action == "reject":
        try:
            # Pass None for user_id — _do_reject will look it up from OWNER_EMAIL
            await _do_reject(request_id, None, "Rejected via Telegram", owner_email)
            notifier.answer_callback(callback_id, "❌ Rejected.")
            notifier.edit_message_reply_markup(
                chat_id, message_id,
                f"❌ <b>Request #{request_id} rejected</b> by @{from_username}",
            )
        except HTTPException as e:
            notifier.answer_callback(callback_id, f"Error: {e.detail}")

    return {"ok": True}
