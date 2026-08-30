"""
connectors/telegram/telegram_adapter.py

Uses Telegram's official Bot API (https://core.telegram.org/bots/api)
via plain HTTP requests — no scraping, no session hijacking, no
automating a personal account.

*** IMPORTANT: this operates as a separate BOT identity ***
This is NOT your personal Telegram account replying automatically in
your own DMs. You create a bot via @BotFather (a few messages, takes
under a minute), get a bot token, and people interact with THAT bot —
a distinct identity you control. This is the officially sanctioned way
to automate Telegram; automating a personal user account through
session-based tools sits in Telegram's restricted territory for
regular accounts and is deliberately NOT what this connector does.

Setup:
1. Message @BotFather on Telegram, send /newbot, follow the prompts.
2. Copy the token it gives you into .env as TELEGRAM_BOT_TOKEN.
3. That's it — no app review, no business account needed.

The token is a credential — never logged, never included in any error
message verbatim (see _redact below), and only ever read from the
environment, matching spec section 9's secret management rules.
"""

import os
import requests
from dotenv import load_dotenv

from connectors.base import PlatformAdapter, IncomingMessage
from database.state_store import get_state, set_state

load_dotenv()

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
OFFSET_STATE_KEY = "telegram_last_update_offset"
POLL_TIMEOUT_SECONDS = 10  # how long a single getUpdates long-poll call waits for new messages


def _redact(text: str, token: str) -> str:
    """Removes the bot token from any string before it could end up in a log or error message."""
    if token:
        return text.replace(token, "[REDACTED_TOKEN]")
    return text


class TelegramAdapter(PlatformAdapter):
    def __init__(self):
        self._token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    @property
    def platform_name(self) -> str:
        return "telegram"

    def is_configured(self) -> bool:
        return bool(self._token)

    def _api_url(self, method: str) -> str:
        return f"{TELEGRAM_API_BASE.format(token=self._token)}/{method}"

    def fetch_incoming_messages(self) -> list[IncomingMessage]:
        if not self.is_configured():
            return []

        last_offset = get_state(OFFSET_STATE_KEY)
        params = {"timeout": POLL_TIMEOUT_SECONDS}
        if last_offset is not None:
            params["offset"] = int(last_offset) + 1

        try:
            resp = requests.get(self._api_url("getUpdates"), params=params, timeout=POLL_TIMEOUT_SECONDS + 5)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(_redact(f"Telegram getUpdates failed: {e}", self._token)) from e

        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(_redact(f"Telegram API returned an error: {data}", self._token))

        messages = []
        highest_update_id = None

        for update in data.get("result", []):
            highest_update_id = update["update_id"]
            message = update.get("message")
            if not message or "text" not in message:
                continue  # skip non-text updates (photos, stickers, etc.) — not handled yet

            sender = message.get("from", {})
            display_name = sender.get("username") or sender.get("first_name") or f"telegram_user_{sender.get('id')}"

            messages.append(IncomingMessage(
                platform_user_id=str(message["chat"]["id"]),
                display_name=display_name,
                text=message["text"],
                message_id=str(message["message_id"]),
                timestamp=str(message.get("date", "")),
            ))

        if highest_update_id is not None:
            set_state(OFFSET_STATE_KEY, str(highest_update_id))

        return messages

    def send_message(self, platform_user_id: str, text: str) -> bool:
        if not self.is_configured():
            raise RuntimeError("Telegram adapter is not configured — set TELEGRAM_BOT_TOKEN in .env first.")

        try:
            resp = requests.post(
                self._api_url("sendMessage"),
                json={"chat_id": platform_user_id, "text": text},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return bool(data.get("ok"))
        except requests.exceptions.RequestException as e:
            raise RuntimeError(_redact(f"Telegram sendMessage failed: {e}", self._token)) from e
