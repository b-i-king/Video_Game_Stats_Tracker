import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from api.core.deps import OwnerUser, require_api_key

router = APIRouter()


class PostInstagramRequest(BaseModel):
    force_type: str | None = None  # "daily" | "historical" | None


def _run_poster(force_type: str | None) -> dict:
    """
    Blocking helper — runs instagram_poster logic synchronously.
    Called via asyncio.to_thread so it doesn't block the event loop.
    """
    from instagram_poster import run_instagram_poster_for_queue

    if force_type == "historical":
        # Directly call the historical branch
        from instagram_poster import (
            PLAYER_ID, get_player_info, get_historical_records_all_games,
            create_instagram_portrait_chart, post_to_instagram,
            generate_trendy_caption, get_posted_content_hash,
        )
        player_name = get_player_info(PLAYER_ID)
        posted_hashes = get_posted_content_hash()
        records = get_historical_records_all_games(PLAYER_ID, posted_hashes)
        if not records:
            raise ValueError("No historical records available.")
        stats = [(r["stat"], r["value"]) for r in records[:3]]
        game_info = records[0].get("game_info", {})
        image_buffer = create_instagram_portrait_chart(
            stats, player_name,
            game_info.get("game_name", ""), game_info.get("game_installment"),
            "Historical Best Performances", "All-Time Records",
        )
        caption = generate_trendy_caption(
            "historical", stats, game_info, player_name,
            "", [], None, 1, None, False,
        )
        success = post_to_instagram(image_buffer, caption)
        if not success:
            raise RuntimeError("post_to_instagram returned False.")
        return {"post_type": "historical", "caption_preview": caption[:200]}

    # Default: use queue runner (handles today/yesterday/historical priority)
    result = run_instagram_poster_for_queue()
    return result


def _build_preview() -> dict:
    """
    Blocking helper — builds a preview without posting.
    """
    import base64
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from instagram_poster import (
        PLAYER_ID, TIMEZONE_STR, get_player_info,
        check_games_on_date, get_stats_for_date_all_games,
        get_historical_records_all_games, create_instagram_portrait_chart,
        generate_trendy_caption, get_posted_content_hash,
    )

    player_name = get_player_info(PLAYER_ID)
    if not player_name:
        raise ValueError(f"No player found for PLAYER_ID={PLAYER_ID}")

    now_local = datetime.now(ZoneInfo(TIMEZONE_STR))
    today     = now_local.date()
    yesterday = today - timedelta(days=1)
    day_of_week = now_local.strftime("%A")

    posted_hashes = get_posted_content_hash()

    today_data     = check_games_on_date(PLAYER_ID, today)
    yesterday_data = check_games_on_date(PLAYER_ID, yesterday) if not today_data else None

    if today_data:
        multi     = get_stats_for_date_all_games(PLAYER_ID, today)
        post_type = "daily_stats"
        title     = "Today's Performance"
        subtitle  = today.strftime("%A, %B %d")
    elif yesterday_data:
        multi     = get_stats_for_date_all_games(PLAYER_ID, yesterday)
        post_type = "recent_stats"
        title     = "Yesterday's Performance"
        subtitle  = yesterday.strftime("%A, %B %d")
    else:
        records = get_historical_records_all_games(PLAYER_ID, posted_hashes)
        if not records:
            raise ValueError("No stats available to preview.")
        stats     = [(r["stat"], r["value"]) for r in records[:3]]
        game_info = records[0].get("game_info", {})
        post_type = "historical"
        title     = "Historical Best Performances"
        subtitle  = "All-Time Records"
        multi     = None

    if multi:
        # Pick game with most rows
        from collections import defaultdict
        counts: dict = defaultdict(int)
        for row in multi:
            counts[row.get("game_id", 0)] += 1
        best_game_id = max(counts, key=lambda k: counts[k])
        game_rows = [r for r in multi if r.get("game_id") == best_game_id]
        stats    = [(r["stat_type"], r["stat_value"]) for r in game_rows[:3]]
        game_info = {"game_name": game_rows[0].get("game_name", ""), "game_installment": game_rows[0].get("game_installment")}

    image_buffer = create_instagram_portrait_chart(
        stats, player_name,
        game_info.get("game_name", ""), game_info.get("game_installment"),
        title, subtitle,
    )
    caption = generate_trendy_caption(
        post_type, stats, game_info, player_name,
        day_of_week, [], None, 1, None, False,
    )

    import base64
    image_buffer.seek(0)
    image_b64 = base64.b64encode(image_buffer.read()).decode()

    return {
        "post_type": post_type,
        "player_name": player_name,
        "title": title,
        "subtitle": subtitle,
        "stats": [{"stat": s[0], "value": s[1]} for s in stats],
        "caption": caption,
        "image_base64": image_b64,
    }


@router.post("/post_instagram", dependencies=[Depends(require_api_key)])
async def post_instagram(body: PostInstagramRequest, _: OwnerUser):
    """
    Owner-only: trigger an Instagram post.
    Requires X-API-KEY header + valid owner JWT.
    """
    try:
        result = await asyncio.to_thread(_run_poster, body.force_type)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "message": "Posted to Instagram successfully.", **result}


@router.get("/preview_instagram", dependencies=[Depends(require_api_key)])
async def preview_instagram(_: OwnerUser):
    """
    Owner-only: preview what would be posted without actually posting.
    Returns post metadata + base64 encoded chart image.
    """
    try:
        result = await asyncio.to_thread(_build_preview)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return result
