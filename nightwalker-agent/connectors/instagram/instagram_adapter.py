"""
connectors/instagram/instagram_adapter.py

Instagram DMs via Meta's Graph API — an official channel, not
scraping or automating a personal login session, per connectors/base.py's
explicit prohibitions.

*** UNLIKE TELEGRAM, THIS IS PUSH, NOT PULL ***
Telegram's Bot API lets a bot poll for new messages (getUpdates).
Instagram (like WhatsApp) offers no equivalent — Meta PUSHES new
messages to a webhook URL you configure, in real time, as they happen.
That means fetch_incoming_messages() below makes NO network call to
Instagram at all: there's nothing to "fetch" from Meta on demand.
Instead it drains database/webhook_inbox_store.py, which
webhooks/webhook_server.py (a SEPARATE, standalone process — see that
file's docstring for why it's kept separate from the dashboard) fills
the instant Meta delivers a message. scripts/run_instagram_bot.py
still polls in a loop exactly like scripts/run_telegram_bot.py, but
what it's polling is your own local database, not Meta's API.

*** SETUP (Meta Developer app, Facebook Login for Business path) ***
This implements the more mature, widely-documented Instagram messaging
integration path: a Facebook Page linked to your Instagram professional
account, using the classic Messenger-style Send API
(POST /me/messages) and webhook payload shape
(entry[].messaging[].message). Meta also offers a separate, newer
"Instagram API with Instagram Login" path (host graph.instagram.com, a
different webhook payload shape — entry[].changes[].value.messages[] —
see developers.facebook.com/documentation/instagram-platform). This
adapter does NOT implement sending via that second path, though
parse_webhook_payload() below defensively also recognizes its webhook
shape (see that function's docstring) so an incoming message isn't
silently dropped if your app happens to be set up that way. If you set
your Meta app up via Instagram Login rather than Facebook Login, tell
me and I'll build the send-side variant for it.

Setup steps:
1. Create a Meta Developer app at developers.facebook.com.
2. Add the "Instagram" (or "Messenger") use case and link your
   Instagram professional account via its connected Facebook Page.
3. Generate an access token with instagram_business_manage_messages
   (or instagram_manage_messages, depending on your app's exact setup)
   and put it in .env as INSTAGRAM_ACCESS_TOKEN.
4. Put the ID your token can send as into .env as INSTAGRAM_SENDER_ID
   (Meta's setup screens call this by different names depending on
   which flow you're in — it's the ID shown next to your connected
   account on the app's Instagram setup page).
5. Put your app's App Secret into .env as INSTAGRAM_APP_SECRET — used
   to verify webhook signatures. Never skip this: an unverified
   webhook endpoint accepts forged messages from anyone who finds the
   URL.
6. Choose your own INSTAGRAM_WEBHOOK_VERIFY_TOKEN (any string you make
   up) and put it in .env too.
7. Run scripts/run_webhook_server.py, expose it publicly (a tunnel
   like ngrok/Cloudflare Tunnel for testing; real hosting for
   production — see that script's docstring), and paste the public
   URL plus your verify token into the Meta app's webhook
   configuration.
8. Run scripts/run_instagram_bot.py.

*** NOT TESTED against a real Meta app or webhook delivery ***
Exactly like Phase 11's desktop automation and Phase 12's recorder:
there's no way to test this against the real Meta API without your
actual credentials and a live webhook delivery. What IS tested (see
scripts/edge_case_tests.py): parse_webhook_payload() against synthetic
payloads matching Meta's published documentation for both known
shapes, and send_message()'s request construction (mocking only the
HTTP call, never this file's own logic). You're the first real test of
an actual Meta webhook hitting this code — if the payload shape
doesn't match what's parsed here, tell me the raw JSON body and I'll
fix the parser immediately rather than guessing.
"""

import os

import requests
from dotenv import load_dotenv

from connectors.base import PlatformAdapter, IncomingMessage
from connectors.meta_shared import verify_signature  # re-exported for webhooks/webhook_server.py
from database import webhook_inbox_store

load_dotenv()

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"

__all__ = ["InstagramAdapter", "verify_signature", "parse_webhook_payload"]


def _redact(text: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    return text


def parse_webhook_payload(payload: dict) -> list[dict]:
    """
    Extracts a list of {"platform_user_id", "display_name", "text",
    "message_id", "timestamp"} dicts from a parsed Instagram webhook
    body. Returns an empty list for payloads with no text messages —
    delivery receipts, read receipts, and echoes of the bot's own sent
    messages are all deliberately skipped, not errors, matching
    Telegram's own text-only handling.

    Tries the classic Messenger-style shape this adapter is built for
    (entry[].messaging[].message.text) first, then also checks the
    other known Meta shape (entry[].changes[].value.messages[]) as a
    defensive fallback, since which one an app actually sends depends
    on how it was set up in the Meta dashboard (see module docstring).
    Recognizing that second shape's incoming messages does NOT mean
    send_message() below can reply via that setup — only that a
    message won't be silently lost while that's sorted out.
    """
    results = []
    for entry in payload.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            message = messaging_event.get("message")
            if not message or message.get("is_echo") or "text" not in message:
                continue
            sender_id = messaging_event.get("sender", {}).get("id")
            if not sender_id:
                continue
            results.append({
                "platform_user_id": str(sender_id),
                "display_name": f"instagram_user_{sender_id}",
                "text": message["text"],
                "message_id": message.get("mid", ""),
                "timestamp": str(messaging_event.get("timestamp", "")),
            })

        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") != "text" or "text" not in msg:
                    continue
                sender_id = msg.get("from")
                if not sender_id:
                    continue
                text_field = msg["text"]
                text = text_field.get("body", "") if isinstance(text_field, dict) else str(text_field)
                results.append({
                    "platform_user_id": str(sender_id),
                    "display_name": f"instagram_user_{sender_id}",
                    "text": text,
                    "message_id": msg.get("id", ""),
                    "timestamp": str(msg.get("timestamp", "")),
                })

    return results


class InstagramAdapter(PlatformAdapter):
    def __init__(self):
        self._access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
        self._sender_id = os.getenv("INSTAGRAM_SENDER_ID", "").strip()

    @property
    def platform_name(self) -> str:
        return "instagram"

    def is_configured(self) -> bool:
        return bool(self._access_token and self._sender_id)

    def fetch_incoming_messages(self) -> list[IncomingMessage]:
        """No network call — see module docstring. Drains the local webhook inbox."""
        rows = webhook_inbox_store.drain(self.platform_name)
        return [
            IncomingMessage(
                platform_user_id=row["platform_user_id"],
                display_name=row["display_name"],
                text=row["text"],
                message_id=row["message_id"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    def send_message(self, platform_user_id: str, text: str) -> bool:
        if not self.is_configured():
            raise RuntimeError(
                "Instagram adapter is not configured — set INSTAGRAM_ACCESS_TOKEN "
                "and INSTAGRAM_SENDER_ID in .env first."
            )

        try:
            resp = requests.post(
                f"{GRAPH_API_BASE}/me/messages",
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={"recipient": {"id": platform_user_id}, "message": {"text": text}},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code >= 400:
                raise RuntimeError(_redact(f"Instagram send failed ({resp.status_code}): {data}", self._access_token))
            return "message_id" in data or "id" in data
        except requests.exceptions.RequestException as e:
            raise RuntimeError(_redact(f"Instagram send request failed: {e}", self._access_token)) from e
