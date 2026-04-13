"""
utils/telegram_utils.py
Telegram push notifications for the Video Game Request bot.

Fails silently if unconfigured — never blocks the request path.

Env vars:
    TELEGRAM_ADMIN_BOT_TOKEN  — from @BotFather
    TELEGRAM_ADMIN_CHAT_ID    — your personal chat ID (send /start to the bot, then
                          call https://api.telegram.org/bot<TOKEN>/getUpdates)
"""

from __future__ import annotations

import logging
import os
import requests

log = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends push notifications to your Telegram chat. Fails silently if unconfigured."""

    def __init__(self) -> None:
        self.token   = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        if self.enabled:
            log.info("Telegram notifications: enabled")
        else:
            log.info("Telegram notifications: disabled (set TELEGRAM_ADMIN_BOT_TOKEN + TELEGRAM_CHAT_ID)")

    def send(self, message: str) -> None:
        """Fire-and-forget plain text message. Never raises."""
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                timeout=8,
            )
        except Exception:
            pass

    def send_game_request(
        self,
        request_id: int,
        user_email: str,
        game_name: str,
        game_installment: str | None,
        game_genre: str | None,
        game_subgenre: str | None,
        approve_url: str,
    ) -> None:
        """
        Send a game request notification with inline Approve / Reject buttons.

        Tapping Approve/Reject sends a callback_query to POST /telegram_webhook,
        which the FastAPI router handles to approve or reject the request.
        """
        if not self.enabled:
            return

        title = f"{game_name}: {game_installment}" if game_installment else game_name
        lines = [
            f"🎮 <b>New Game Request #{request_id}</b>",
            f"From: {user_email}",
            f"Game: <b>{title}</b>",
        ]
        if game_genre:
            lines.append(f"Genre: {game_genre}")
        if game_subgenre:
            lines.append(f"Subgenre: {game_subgenre}")

        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": "\n".join(lines),
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {
                                "text": "✅ Approve",
                                "callback_data": f"approve:{request_id}",
                            },
                            {
                                "text": "❌ Reject",
                                "callback_data": f"reject:{request_id}",
                            },
                        ]]
                    },
                },
                timeout=8,
            )
        except Exception:
            pass

    def answer_callback(self, callback_query_id: str, text: str) -> None:
        """Acknowledge a Telegram callback query (removes the loading spinner)."""
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
                timeout=8,
            )
        except Exception:
            pass

    def edit_message_reply_markup(self, chat_id: str | int, message_id: int, text: str) -> None:
        """Replace the inline keyboard with a plain status line after action is taken."""
        if not self.enabled:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/editMessageText",
                json={
                    "chat_id":    chat_id,
                    "message_id": message_id,
                    "text":       text,
                    "parse_mode": "HTML",
                },
                timeout=8,
            )
        except Exception:
            pass


# Module-level singleton — import and use directly
notifier = TelegramNotifier()
