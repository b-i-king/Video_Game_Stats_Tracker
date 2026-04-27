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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

_DISPLAY_TZ = ZoneInfo(os.getenv("DISPLAY_TIMEZONE", "America/New_York"))


def _fmt_played_at(played_at_iso: str) -> str:
    try:
        dt = datetime.fromisoformat(played_at_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(_DISPLAY_TZ)
        h = local.hour
        tz_name = local.tzname() or ""
        return (
            local.strftime("%b %d, %Y")
            + f" {h % 12 or 12}:{local.minute:02d}"
            + (" AM" if h < 12 else " PM")
            + (f" {tz_name}" if tz_name else "")
        )
    except Exception:
        return played_at_iso

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
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/{method}",
                json=payload,
                timeout=8,
            )
            if resp.ok:
                log.info("Telegram %s OK → %s", method, self.channel_id)
            else:
                log.warning("Telegram %s failed %s: %s", method, resp.status_code, resp.text[:300])
        except Exception as exc:
            log.warning("Telegram %s request error: %s", method, exc)

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
        stat_line = "  |  ".join(stat_parts[:3])

        played_str = _fmt_played_at(played_at_iso)

        lines = [
            f"🎮 <b>{title}</b>",
            f"👤 {player_name}",
        ]
        if stat_line:
            lines.append(f"📊 {stat_line}")
        lines.append(f"📅 {played_str}")

        payload: dict = {
            "chat_id":                  self.channel_id,
            "text":                     "\n".join(lines),
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        }

        if self.site_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "📊 Track Your Stats", "url": self.site_url},
                ]]
            }

        self._post("sendMessage", payload)

    def post_session_with_photo(
        self,
        game_name:        str,
        game_installment: str | None,
        player_name:      str,
        stats:            list[dict],
        played_at_iso:    str,
        photo_url:        str,
        win:              int | None = None,
    ) -> None:
        """Post a session summary to the channel with a chart photo attached."""
        title = f"{game_name}: {game_installment}" if game_installment else game_name

        result_str = ""
        if win == 1:
            result_str = " · Win ✅"
        elif win == 0:
            result_str = " · Loss ❌"

        stat_parts = [
            f"{s['stat_type']}: <b>{s['stat_value']}</b>"
            for s in stats
            if s.get("stat_type") and s.get("stat_value") is not None
        ]

        played_str = _fmt_played_at(played_at_iso)

        lines = [
            f"🎮 <b>{title}</b>{result_str}",
            f"👤 {player_name}",
            f"📅 {played_str}",
        ]
        if stat_parts:
            lines.append("📊 " + "  |  ".join(stat_parts[:3]))

        payload: dict = {
            "chat_id":    self.channel_id,
            "photo":      photo_url,
            "caption":    "\n".join(lines),
            "parse_mode": "HTML",
        }

        if self.site_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "📊 Track Your Stats", "url": self.site_url},
                ]]
            }

        self._post("sendPhoto", payload)

    # ── Bot command replies ───────────────────────────────────────────────────

    def reply(self, chat_id: int | str, text: str) -> None:
        """Send a plain reply to a chat (used for bot command responses)."""
        self._post("sendMessage", {
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
        })

    def reply_with_keyboard(
        self,
        chat_id:  int | str,
        text:     str,
        keyboard: list[list[dict]],
    ) -> None:
        """Send a reply with an inline keyboard (e.g. web_app launch buttons)."""
        self._post("sendMessage", {
            "chat_id":                  chat_id,
            "text":                     text,
            "parse_mode":               "HTML",
            "disable_web_page_preview": True,
            "reply_markup":             {"inline_keyboard": keyboard},
        })

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        """Acknowledge a callback query (removes the Telegram loading spinner)."""
        self._post("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text":              text,
        })


# Module-level singleton — import and use directly
broadcaster = TelegramBroadcaster()
