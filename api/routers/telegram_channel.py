"""
Telegram broadcast bot webhook — handles commands from channel subscribers.

Completely separate from /telegram_webhook (game-requests admin bot).

Endpoints:
  POST /telegram_channel_webhook  — Telegram sends all bot updates here

Bot commands:
  /start | /help   — welcome + command list
  /link | /website — web app link
  /lastsession     — live recap of the owner's most recent session (DB query)
  /premium         — premium tier upsell + upgrade link
  /affiliate       — referral program info
  /instagram  /twitter  /tiktok  /youtube  /twitch
  /discord    /threads  /facebook /linkedin
  /donate     /linktree — social + donation links

Setup (one-time, run once after deploying):
  curl -X POST "https://api.telegram.org/bot<TELEGRAM_BROADCAST_BOT_TOKEN>/setWebhook" \\
       -d "url=https://<your-api>/api/telegram_channel_webhook" \\
       -d "secret_token=<TELEGRAM_BROADCAST_WEBHOOK_SECRET>"

Env vars:
  TELEGRAM_BROADCAST_BOT_TOKEN      — broadcast bot token (BotFather)
  TELEGRAM_BROADCAST_WEBHOOK_SECRET — optional HMAC guard (recommended in prod)
  SITE_URL                          — e.g. https://yourdomain.com
  REFERRAL_COMMISSION_PCT           — integer (default 10)
  SOCIAL_INSTAGRAM_URL
  SOCIAL_TWITTER_URL
  SOCIAL_TIKTOK_URL
  SOCIAL_YOUTUBE_URL
  SOCIAL_TWITCH_URL
  SOCIAL_DISCORD_URL
  SOCIAL_THREADS_URL
  SOCIAL_FACEBOOK_URL
  SOCIAL_LINKEDIN_URL
  SOCIAL_DONATE_URL
  SOCIAL_LINKTREE_URL
  OWNER_EMAIL                       — scopes /lastsession to your account
"""

import os
from datetime import datetime, timezone, timedelta

import requests as _requests
from fastapi import APIRouter, Header, HTTPException, Request

from utils.telegram_broadcast import broadcaster
from api.core import database as _db

router = APIRouter()

_WEBHOOK_SECRET = os.getenv("TELEGRAM_BROADCAST_WEBHOOK_SECRET", "")

# ── Social platform registry ──────────────────────────────────────────────────
# (slug, emoji, display_name, env_var)
_PLATFORMS: list[tuple[str, str, str, str]] = [
    ("instagram", "📸", "Instagram",   "SOCIAL_INSTAGRAM_URL"),
    ("twitter",   "🐦", "Twitter / X", "SOCIAL_TWITTER_URL"),
    ("tiktok",    "🎵", "TikTok",      "SOCIAL_TIKTOK_URL"),
    ("youtube",   "▶️", "YouTube",     "SOCIAL_YOUTUBE_URL"),
    ("twitch",    "🟣", "Twitch",      "SOCIAL_TWITCH_URL"),
    ("discord",   "💬", "Discord",     "SOCIAL_DISCORD_URL"),
    ("threads",   "🧵", "Threads",     "SOCIAL_THREADS_URL"),
    ("facebook",  "📘", "Facebook",    "SOCIAL_FACEBOOK_URL"),
    ("linkedin",  "💼", "LinkedIn",    "SOCIAL_LINKEDIN_URL"),
    ("donate",    "❤️", "Donate",      "SOCIAL_DONATE_URL"),
    ("linktree",  "🌳", "Linktree",    "SOCIAL_LINKTREE_URL"),
]

_PLATFORM_SLUGS = {p[0] for p in _PLATFORMS}


def _url(env_var: str) -> str:
    return os.getenv(env_var, "").strip()


# ── /lastsession DB query ─────────────────────────────────────────────────────

def _owner_emails() -> list[str]:
    """Return all owner emails from the OWNER_EMAILS comma-separated env var."""
    raw = os.getenv("OWNER_EMAILS", "").strip()
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


async def _fetch_last_session() -> str:
    """Pull the most recent session across all owner accounts. Returns HTML."""
    if _db.personal_pool is None:
        return "⚠️ Database unavailable right now."

    emails = _owner_emails()
    if not emails:
        return "⚠️ OWNER_EMAILS is not configured."

    try:
        async with _db.personal_pool.acquire() as conn:
            # Match any email in the owner list
            user_id = await conn.fetchval(
                "SELECT user_id FROM dim.dim_users WHERE user_email = ANY($1::text[])",
                emails,
            )
            if not user_id:
                return "⚠️ Owner account not found."

            rows = await conn.fetch("""
                WITH latest AS (
                    SELECT gs.played_at, gs.game_id, gs.player_id
                    FROM fact.fact_game_stats gs
                    JOIN dim.dim_players p ON gs.player_id = p.player_id
                    WHERE p.user_id = $1
                    ORDER BY gs.played_at DESC
                    LIMIT 1
                )
                SELECT
                    g.game_name,
                    g.game_installment,
                    p.player_name,
                    gs.stat_type,
                    gs.stat_value,
                    gs.win,
                    gs.game_mode,
                    gs.played_at
                FROM fact.fact_game_stats gs
                JOIN dim.dim_games   g  ON gs.game_id   = g.game_id
                JOIN dim.dim_players p  ON gs.player_id = p.player_id
                JOIN latest lb
                  ON gs.played_at = lb.played_at
                 AND gs.game_id   = lb.game_id
                 AND gs.player_id = lb.player_id
                ORDER BY gs.stat_value DESC NULLS LAST
                LIMIT 3
            """, user_id)

        if not rows:
            return "No sessions recorded yet."

        first       = rows[0]
        installment = first["game_installment"]
        title       = f"{first['game_name']}: {installment}" if installment else first["game_name"]
        win_val     = first["win"]
        result_str  = " · Win ✅" if win_val == 1 else (" · Loss ❌" if win_val == 0 else "")
        mode_str    = f" · {first['game_mode']}" if first["game_mode"] else ""

        try:
            played_str = first["played_at"].strftime("%b %d, %Y %H:%M")
        except Exception:
            played_str = str(first["played_at"])

        stat_parts = [
            f"{r['stat_type']}: <b>{r['stat_value']}</b>"
            for r in rows
            if r["stat_type"] and r["stat_value"] is not None
        ]

        lines = [
            f"🎮 <b>{title}</b>{mode_str}{result_str}",
            f"👤 {first['player_name']}",
            f"📅 {played_str}",
        ]
        if stat_parts:
            lines.append("📊 " + "  |  ".join(stat_parts[:5]))

        if broadcaster.site_url:
            lines.append(f'🔗 <a href="{broadcaster.site_url}">View full stats</a>')

        return "\n".join(lines)

    except Exception as exc:
        return f"⚠️ Could not fetch last session: {exc}"


# ── Webhook handler ───────────────────────────────────────────────────────────

@router.post("/telegram_channel_webhook")
async def telegram_channel_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    if _WEBHOOK_SECRET and x_telegram_bot_api_secret_token != _WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()

    # ── pre_checkout_query — must answer within 10 s ──────────────────────────
    pcq = update.get("pre_checkout_query")
    if pcq:
        token = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
        try:
            _requests.post(
                f"https://api.telegram.org/bot{token}/answerPreCheckoutQuery",
                json={"pre_checkout_query_id": pcq["id"], "ok": True},
                timeout=8,
            )
        except Exception:
            pass
        return {"ok": True}

    message = update.get("message") or update.get("channel_post")
    if not message:
        return {"ok": True}

    # ── successful_payment — grant Premium ───────────────────────────────────
    sp = message.get("successful_payment")
    if sp and sp.get("currency") == "XTR":
        payload     = sp.get("invoice_payload", "")
        tg_from_id  = message.get("from", {}).get("id")
        # payload format: "premium_monthly_{user_id}"
        try:
            user_id = int(payload.split("_")[-1])
        except (ValueError, IndexError):
            user_id = None

        if user_id and _db.public_pool:
            try:
                expires = datetime.now(timezone.utc) + timedelta(days=30)
                async with _db.public_pool.acquire() as pconn:
                    await pconn.execute("""
                        INSERT INTO app.subscriptions
                            (user_id, plan, billing_interval, started_at, expires_at)
                        VALUES ($1, 'premium', 'month', NOW(), $2)
                        ON CONFLICT (user_id) DO UPDATE
                            SET plan         = 'premium',
                                started_at   = NOW(),
                                expires_at   = EXCLUDED.expires_at,
                                cancelled_at = NULL
                    """, user_id, expires)
                print(f"[stars] Premium activated for user_id={user_id} via Stars")
            except Exception as exc:
                print(f"[stars] Failed to activate Premium: {exc}")

        # Confirm to the user in chat
        if tg_from_id:
            broadcaster.reply(
                tg_from_id,
                "✅ <b>Premium activated!</b>\n\nYou now have full access for 30 days.\n"
                + (f'<a href="{broadcaster.site_url}">Open the app</a>' if broadcaster.site_url else ""),
            )
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    text    = (message.get("text") or "").strip()
    if not text.startswith("/") or not chat_id:
        return {"ok": True}

    # /command@BotUsername → /command, lowercase
    command = text.split()[0].split("@")[0].lower()
    site    = broadcaster.site_url
    pct     = os.getenv("REFERRAL_COMMISSION_PCT", "10")

    # ── /start | /help ────────────────────────────────────────────────────────
    if command in ("/start", "/help"):
        lines = [
            "👋 <b>Welcome to Video Game Stats Tracker!</b>",
            "",
            "📊 Log every session, track KPIs, and see your performance trends over time.",
            "",
            "What you can do here:",
            "• /link         — Open the web app",
            "• /lastsession  — See your most recent session",
            "• /premium      — Upgrade for full access",
            "• /affiliate    — Earn 10% lifetime commission by referring friends",
            "• /linktree     — All our social links",
            "",
            "🎮 Sessions are posted to the channel automatically as they're logged.",
            "",
            "Tap the button below to open the app 👇",
        ]
        if broadcaster.site_url:
            broadcaster.reply(chat_id, "\n".join(lines))
        else:
            broadcaster.reply(chat_id, "\n".join(lines))

    # ── /link | /website ──────────────────────────────────────────────────────
    elif command in ("/link", "/website"):
        if site:
            broadcaster.reply(chat_id, f'📊 <b>Game Stats Tracker</b>\n<a href="{site}">{site}</a>')
        else:
            broadcaster.reply(chat_id, "⚠️ Site URL not configured yet.")

    # ── /premium ──────────────────────────────────────────────────────────────
    elif command == "/premium":
        lines = [
            "⭐ <b>Premium Plan</b>",
            "",
            "Unlock the full experience:",
            "• Up to 5 player profiles",
            "• Leaderboard access",
            "• Monthly community digest",
            "• Data export",
        ]
        if site:
            lines += ["", f'👉 <a href="{site}/account">Upgrade now</a>']
        broadcaster.reply(chat_id, "\n".join(lines))

    # ── /affiliate ────────────────────────────────────────────────────────────
    elif command == "/affiliate":
        lines = [
            f"🤝 <b>Referral Program — {pct}% Lifetime Commission</b>",
            "",
            f"Earn {pct}% of every payment made by users you refer — for as long as they stay subscribed.",
            "",
            "How it works:",
            f"1. Sign in at the web app to get your referral link",
            f"2. Share it anywhere",
            f"3. Earn {pct}% for every Premium payment they make",
        ]
        if site:
            lines += ["", f'👉 <a href="{site}/account">Get your link</a>']
        broadcaster.reply(chat_id, "\n".join(lines))

    # ── /lastsession ──────────────────────────────────────────────────────────
    elif command == "/lastsession":
        caption = await _fetch_last_session()
        broadcaster.reply(chat_id, caption)

    # ── Individual social platform commands ───────────────────────────────────
    elif command[1:] in _PLATFORM_SLUGS:
        slug  = command[1:]
        entry = next(p for p in _PLATFORMS if p[0] == slug)
        _, emoji, display_name, env_var = entry

        if slug == "donate":
            link = _url(env_var)
            if link:
                broadcaster.reply(
                    chat_id,
                    f'{emoji} <b>Support the Project</b>\n'
                    f'Every contribution helps keep the tracker running!\n'
                    f'<a href="{link}">{link}</a>',
                )
            else:
                broadcaster.reply(chat_id, f"⚠️ Donation link not configured (set {env_var}).")

        elif slug == "linktree":
            lt_url   = _url(env_var)
            sections: list[str] = []
            if lt_url:
                sections.append(f'{emoji} <b>All Links</b>\n<a href="{lt_url}">{lt_url}</a>')

            socials: list[str] = []
            for p_slug, p_emoji, p_name, p_env in _PLATFORMS:
                if p_slug == "linktree":
                    continue
                p_link = _url(p_env)
                if p_link:
                    socials.append(f'{p_emoji} <a href="{p_link}">{p_name}</a>')
            if site:
                socials.append(f'📊 <a href="{site}">Game Stats Tracker</a>')

            if socials:
                sections.append("\n".join(socials))

            if sections:
                broadcaster.reply(chat_id, "\n\n".join(sections))
            else:
                broadcaster.reply(chat_id, "⚠️ No social links configured yet.")

        else:
            link = _url(env_var)
            if link:
                broadcaster.reply(chat_id, f'{emoji} <b>{display_name}</b>\n<a href="{link}">{link}</a>')
            else:
                broadcaster.reply(chat_id, f"⚠️ {display_name} link not configured (set {env_var}).")

    return {"ok": True}
