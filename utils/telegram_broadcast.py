"""
utils/telegram_broadcast.py
Telegram broadcast channel + bot command replies.

Completely separate from telegram_utils.py (game-requests admin bot).
This bot posts public session summaries to a Telegram channel and
responds to subscriber commands.

Env vars:
    TELEGRAM_BROADCAST_BOT_TOKEN    — from @BotFather (a new, separate bot)
    TELEGRAM_CHANNEL_ID             — @channelname or -100xxxxxxxxxx
    SITE_URL                        — public web app URL, e.g. https://yourdomain.com
"""

from __future__ import annotations

import logging
import os
import requests

log = logging.getLogger(__name__)


class TelegramBroadcaster:
    """Posts session summaries to a Telegram channel and handles bot command replies. Fails silently."""

    def __init__(self) -> None:
        self.token      = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
        self.site_url   = os.getenv("SITE_URL", "").rstrip("/")
        self.enabled    = bool(self.token and self.channel_id)
        if self.enabled:
            log.info("Telegram broadcaster: enabled → %s", self.channel_id)
        else:
            log.info(
                "Telegram broadcaster: disabled "
                "(set TELEGRAM_BROADCAST_BOT_TOKEN + TELEGRAM_CHANNEL_ID)"
            )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _post(self, method: str, payload: dict) -> None:
        """Fire-and-forget Telegram API call. Never raises."""
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                json=payload,
                timeout=8,
            )
        except Exception:
            pass

    # ── Channel posting ───────────────────────────────────────────────────────

    def post_session(
        self,
        game_name:        str,
        game_installment: str | None,
        player_name:      str,
        stats:            list[dict],   # [{"stat_type": "Kills", "stat_value": 12}, ...]
        played_at_iso:    str,
    ) -> None:
        """Post a new session summary to the broadcast channel."""
        title = f"{game_name}: {game_installment}" if game_installment else game_name

        stat_parts = [
            f"{s['stat_type']}: <b>{s['stat_value']}</b>"
            for s in stats
            if s.get("stat_type") and s.get("stat_value") is not None
        ]
        stat_line = "  |  ".join(stat_parts[:5])  # cap at 5 to keep it readable

        try:
            from datetime import datetime
            dt = datetime.fromisoformat(played_at_iso.replace("Z", "+00:00"))
            played_str = dt.strftime("%b %d, %Y")
        except Exception:
            played_str = played_at_iso

        lines = [
            f"🎮 <b>{title}</b>",
            f"👤 {player_name}",
        ]
        if stat_line:
            lines.append(f"📊 {stat_line}")
        lines.append(f"📅 {played_str}")
        if self.site_url:
            lines.append(f'🔗 <a href="{self.site_url}">Track your own stats</a>')

        self._post("sendMessage", {
            "chat_id":                  self.channel_id,
            "text":                     "\n".join(lines),
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })

    # ── Bot command replies ───────────────────────────────────────────────────

    def reply(self, chat_id: int | str, text: str) -> None:
        """Send a plain reply to a chat (used for bot command responses)."""
        self._post("sendMessage", {
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        """Acknowledge a callback query (removes the Telegram loading spinner)."""
        self._post("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text":              text,
        })


# Module-level singleton — import and use directly
broadcaster = TelegramBroadcaster()
