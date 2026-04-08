"""
Post queue routes — Owner only.

  X-Cron-Secret protected (called by Render cron job, no JWT):
    POST /process_queue   — claim + fire oldest pending item, housekeeping

  JWT OwnerUser protected:
    GET  /queue_status    — pending/processing/sent/failed counts
    POST /retry_failed    — reset all failed items back to pending
"""

import asyncio
from fastapi import APIRouter, Header, HTTPException, status

from api.core.config import get_settings
from api.core.deps import OwnerUser
from utils.queue_utils import (
    get_oldest_pending,
    mark_status,
    get_queue_counts,
    reset_failed_to_pending,
    reset_stale_processing,
    purge_old_sent,
)
from utils.ifttt_utils import trigger_ifttt_post

router = APIRouter()


def _check_cron_secret(x_cron_secret: str | None) -> None:
    secret = get_settings().cron_secret
    if not secret or x_cron_secret != secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/process_queue")
async def process_queue(x_cron_secret: str | None = Header(default=None)):
    """
    Process the oldest pending post and fire the IFTTT webhook.
    Protected by X-Cron-Secret header — called by the Render cron job.
    Runs housekeeping (stale reset + purge) before processing.
    """
    _check_cron_secret(x_cron_secret)

    results = {"processed": 0, "status": None, "queue_id": None, "purged": 0, "stale_reset": 0}

    # Housekeeping: reset rows stuck in 'processing' > 10 min
    try:
        stale = await asyncio.to_thread(reset_stale_processing, 10)
        results["stale_reset"] = stale
        if stale:
            print(f"[queue] Reset {stale} stale processing row(s) back to pending.")
    except Exception as e:
        print(f"[queue] Stale reset error (non-fatal): {e}")

    # Housekeeping: purge sent rows older than 7 days
    try:
        purged = await asyncio.to_thread(purge_old_sent, 7)
        results["purged"] = purged
        if purged:
            print(f"[queue] Purged {purged} old sent post(s) from queue.")
    except Exception as e:
        print(f"[queue] Purge error (non-fatal): {e}")

    # Claim oldest pending item atomically
    try:
        item = await asyncio.to_thread(get_oldest_pending)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue read failed: {e}")

    if not item:
        results["status"] = "empty"
        return results

    queue_id = item["queue_id"]
    results["queue_id"] = queue_id

    try:
        success = await asyncio.to_thread(
            trigger_ifttt_post, item["image_url"], item["caption"], item["platform"]
        )
        new_status = "sent" if success else "failed"
        await asyncio.to_thread(mark_status, queue_id, new_status)
        results["processed"] = 1
        results["status"]    = new_status
        print(f"[queue] Item {queue_id} ({item['platform']}): {new_status}")
        return results
    except Exception as e:
        try:
            await asyncio.to_thread(mark_status, queue_id, "failed")
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue_status")
async def queue_status(user: OwnerUser):
    """Return pending/processing/sent/failed counts. Owner only."""
    try:
        counts = await asyncio.to_thread(get_queue_counts)
        print(f"[queue] Status requested by {user['email']}: {counts}")
        return counts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry_failed")
async def retry_failed(user: OwnerUser):
    """Reset all failed queue items back to pending. Owner only."""
    try:
        count = await asyncio.to_thread(reset_failed_to_pending)
        print(f"[queue] {user['email']} reset {count} failed post(s) to pending.")
        return {"reset_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
