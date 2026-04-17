"""
Owner-only social media pipeline.

Generates bar/line charts, uploads to GCS, and queues/triggers Twitter & Instagram
posts after a stat submission. Designed to run in a background thread via
``asyncio.to_thread`` so it never blocks the FastAPI event loop.

Usage (from add_stats):
    import asyncio
    from utils.social_pipeline import run_social_media_pipeline
    asyncio.create_task(asyncio.to_thread(run_social_media_pipeline, ...))
"""

from __future__ import annotations

import traceback


def run_social_media_pipeline(
    player_id: int,
    player_name: str,
    game_id: int,
    game_name: str,
    game_installment: str | None,
    stats: list[dict],
    is_live: bool,
    credit_style: str,
    queue_platforms: list[str],
    played_at_iso: str = "",
    win: int | None = None,
) -> None:
    """Generate charts, upload to GCS, and queue/trigger social posts.

    Opens its own psycopg2 connection (personal DB) so the caller can return
    immediately without waiting for chart generation or network uploads.

    Args:
        player_id:        DB player_id for the owner.
        player_name:      Display name used in chart titles and captions.
        game_id:          DB game_id.
        game_name:        Game franchise name.
        game_installment: Game installment/subtitle, or None.
        stats:            List of stat dicts (model_dump() of each StatRow).
        is_live:          Whether the session was a live stream.
        credit_style:     Caption credit style ('shoutout', 'minimal', etc.).
        queue_platforms:  Platforms to enqueue rather than immediately post
                          e.g. ['twitter', 'instagram']. Empty list = post now.
    """
    import psycopg2
    from api.core.config import get_settings
    from utils.chart_utils import (
        generate_bar_chart,
        generate_line_chart,
        get_stat_history_from_db,
        generate_interactive_chart,
    )
    from utils.gcs_utils import upload_chart_to_gcs, upload_interactive_chart_to_gcs
    from utils.ifttt_utils import trigger_ifttt_post, generate_post_caption
    from utils.queue_utils import enqueue_post

    pg = None
    try:
        dsn = get_settings().personal_db_url
        pg = psycopg2.connect(dsn, sslmode="require")
        cur = pg.cursor()

        batch_game_mode: str | None = next(
            (s.get("game_mode") for s in stats if s.get("game_mode") and str(s["game_mode"]).strip()),
            None,
        )

        cur.execute(
            "SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats "
            "WHERE player_id = %s AND game_id = %s",
            (player_id, game_id),
        )
        games_played: int = cur.fetchone()[0]

        print(f"📊 [bg] Social pipeline: games_played={games_played}, player={player_name}, game={game_name}")

        cur.execute("""
            SELECT stat_type FROM fact.fact_game_stats
            WHERE game_id = %s AND player_id = %s AND stat_type IS NOT NULL
            GROUP BY stat_type
            HAVING COUNT(*) >= 2
            ORDER BY AVG(stat_value) DESC, STDDEV(stat_value) DESC NULLS LAST, COUNT(*) DESC
            LIMIT 3
        """, (game_id, player_id))
        top_stats: list[str] = [r[0] for r in cur.fetchall()]

        if games_played == 1:
            stat_data: dict = {}
            for i, s in enumerate(stats[:3], 1):
                st = s.get("stat_type")
                if not st:
                    continue
                stat_data[f"stat{i}"] = {
                    "label": st,
                    "value": s.get("stat_value", 0),
                    "prev_value": None,
                }
                cur.execute("""
                    SELECT stat_value FROM fact.fact_game_stats
                    WHERE player_id = %s AND game_id = %s AND stat_type = %s
                    ORDER BY played_at DESC LIMIT 2
                """, (player_id, game_id, st))
                prev_rows = cur.fetchall()
                if len(prev_rows) > 1:
                    stat_data[f"stat{i}"]["prev_value"] = prev_rows[1][0]

            buf_tw = generate_bar_chart(stat_data, player_name, game_name, game_installment, size="twitter",   game_mode=batch_game_mode)
            buf_ig = generate_bar_chart(stat_data, player_name, game_name, game_installment, size="instagram", game_mode=batch_game_mode)
            chart_type = "bar"
            stat_data_for_caption = stat_data
            interactive_data = stat_data

        elif games_played > 1:
            cur.execute(
                "SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats "
                "WHERE player_id = %s AND game_id = %s "
                "AND played_at >= NOW() - INTERVAL '30 days'",
                (player_id, game_id),
            )
            sessions_30d: int = cur.fetchone()[0]

            stat_history = get_stat_history_from_db(cur, player_id, game_id, top_stats, days_back=30)
            buf_tw = generate_line_chart(stat_history, player_name, game_name, game_installment, size="twitter",   game_mode=batch_game_mode)
            buf_ig = generate_line_chart(stat_history, player_name, game_name, game_installment, size="instagram", game_mode=batch_game_mode)
            chart_type = "line"
            stat_data_for_caption = {}
            for i in range(1, 4):
                key = f"stat{i}"
                if key in stat_history and stat_history[key]:
                    vals  = stat_history[key].get("values", [])
                    label = stat_history[key].get("label", "")
                    cur.execute("""
                        SELECT stat_value FROM fact.fact_game_stats
                        WHERE player_id = %s AND game_id = %s AND stat_type = %s
                        ORDER BY played_at DESC LIMIT 2
                    """, (player_id, game_id, label))
                    prev_rows = cur.fetchall()
                    stat_data_for_caption[key] = {
                        "label": label,
                        "value": vals[-1] if vals else 0,
                        "prev_value": prev_rows[1][0] if len(prev_rows) > 1 else None,
                    }
            interactive_data = stat_history

        else:
            print("⚠️  [bg] No sessions found — pipeline aborted.")
            return

        # --- Interactive chart → GCS (non-fatal) ---
        interactive_url: str | None = None
        try:
            html = generate_interactive_chart(
                chart_type, interactive_data, player_name, game_name,
                game_installment=game_installment, game_mode=batch_game_mode,
            )
            interactive_url = upload_interactive_chart_to_gcs(html, player_name, game_name, game_installment)
            print(f"✅ [bg] Interactive chart uploaded: {interactive_url}")
        except Exception as e:
            print(f"⚠️  [bg] Interactive chart upload failed (non-fatal): {e}")

        # --- Twitter chart ---
        twitter_url = upload_chart_to_gcs(
            buf_tw, player_name, game_name, chart_type, platform="twitter",
        )
        if twitter_url:
            # Post to Telegram channel with the chart image — runs here so the
            # photo URL is guaranteed ready (avoids race condition with stats.py).
            try:
                from utils.telegram_broadcast import broadcaster
                # Build top-3 stat list from stat_data_for_caption (already ranked)
                top_stats_display = [
                    {"stat_type": v["label"], "stat_value": v["value"]}
                    for v in stat_data_for_caption.values()
                    if v.get("label") and v.get("stat_value") is not None
                ]
                broadcaster.post_session_with_photo(
                    game_name=game_name,
                    game_installment=game_installment,
                    player_name=player_name,
                    stats=top_stats_display,
                    played_at_iso=played_at_iso,
                    photo_url=twitter_url,
                    win=win,
                )
                print(f"[bg] Telegram broadcast attempted → enabled={broadcaster.enabled}, channel={broadcaster.channel_id!r}")
            except Exception as _tg_err:
                print(f"⚠️  [bg] Telegram broadcast failed (non-fatal): {_tg_err}")
            caption = generate_post_caption(
                player_name, game_name, game_installment, stat_data_for_caption,
                games_played, platform="twitter", is_live=is_live,
                credit_style=credit_style, game_mode=batch_game_mode,
                interactive_url=interactive_url,
                sessions_30d=sessions_30d if chart_type == "line" else None,
            )
            if "twitter" in queue_platforms:
                qid = enqueue_post(player_id, "twitter", twitter_url, caption)
                print(f"📥 [bg] Twitter queued (queue_id={qid})")
            else:
                ok = trigger_ifttt_post(twitter_url, caption, "twitter")
                print(f"{'✅' if ok else '⚠️'} [bg] Twitter {'triggered' if ok else 'failed'}")
        else:
            print("⚠️  [bg] Twitter chart upload failed — post skipped.")

        # --- Instagram chart (only if queued) ---
        if "instagram" in queue_platforms:
            instagram_url = (
                upload_chart_to_gcs(
                    buf_ig, player_name, game_name, chart_type,
                    platform="instagram", storage_option="game",
                    game_installment=game_installment, game_mode=batch_game_mode,
                )
                or upload_chart_to_gcs(
                    buf_ig, player_name, game_name, chart_type,
                    platform="instagram", storage_option="week",
                )
            )
            if instagram_url:
                ig_caption = generate_post_caption(
                    player_name, game_name, game_installment, stat_data_for_caption,
                    games_played, platform="instagram", is_live=is_live,
                    credit_style=credit_style, game_mode=batch_game_mode,
                    sessions_30d=sessions_30d if chart_type == "line" else None,
                )
                qid = enqueue_post(player_id, "instagram", instagram_url, ig_caption)
                print(f"📥 [bg] Instagram queued (queue_id={qid})")
            else:
                print("⚠️  [bg] Instagram chart upload failed — post skipped.")

    except Exception as e:
        print(f"⚠️  [bg] Social media pipeline error (stats already saved): {e}")
        traceback.print_exc()
    finally:
        if pg:
            pg.close()
