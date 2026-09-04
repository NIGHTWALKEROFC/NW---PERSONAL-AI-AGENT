"""
connectors/whatsapp/whatsapp_adapter.py

WhatsApp via Meta's official WhatsApp Business Platform (Cloud API) —
NOT a personal WhatsApp account, and NOT one of the unofficial
libraries (whatsapp-web.js, Baileys, pywhatkit, etc.) that automate a
personal account by reverse-engineering WhatsApp Web. Those violate
WhatsApp's terms and risk the number being banned — exactly the "ban
evasion" automation connectors/base.py's module docstring rules out.
"WhatsApp" and "WhatsApp Business" aren't two separate integrations
here: the Cloud API is the one official path, and it's the only one
this adapter implements.

*** UNLIKE TELEGRAM, THIS IS PUSH, NOT PULL ***
See connectors/instagram/instagram_adapter.py's docstring for the full
explanation — it applies identically here. Short version:
fetch_incoming_messages() below makes no network call; it drains
database/webhook_inbox_store.py, which webhooks/webhook_server.py
fills as Meta delivers messages.

*** THE 24-HOUR CUSTOMER SERVICE WINDOW ***
Meta only allows free-form text replies within 24 hours of the last
message a user sent you. Outside that window, sending requires a
pre-approved message template — a separate Meta feature, NOT
implemented here (templates need approval through the Meta Business
dashboard and don't fit this project's "just send my normal reply"
model). send_message() below raises a clear, specific RuntimeError if
Meta rejects a send for this reason (error code 131047) rather than
looking like a generic failure — so it's obvious immediately why a
message didn't go through, instead of assuming something's broken.

*** SETUP (Meta Developer app, WhatsApp Business Platform / Cloud API) ***
1. Create a Meta Developer app at developers.facebook.com and add the
   "WhatsApp" use case — this gives you a free test phone number to
   start with, no need to use your real number for development.
2. From the app's WhatsApp > API Setup page, copy:
     - an access token (temporary or permanent) -> .env WHATSAPP_ACCESS_TOKEN
     - the Phone Number ID (NOT the phone number itself) -> .env WHATSAPP_PHONE_NUMBER_ID
3. Copy the app's App Secret (App Settings > Basic) -> .env
   WHATSAPP_APP_SECRET — used to verify webhook signatures.
4. Choose your own WHATSAPP_WEBHOOK_VERIFY_TOKEN (any string) and put
   it in .env too.
5. Run scripts/run_webhook_server.py, expose it publicly, and
   configure the callback URL plus verify token on the WhatsApp >
   Configuration page in the Meta app dashboard.
6. Run scripts/run_whatsapp_bot.py.

*** NOT TESTED against a real Meta app or webhook delivery ***
Same honesty as instagram_adapter.py and everywhere else in this
project: parse_webhook_payload() is tested against synthetic payloads
matching Meta's published docs, and send_message()'s request
construction is tested by mocking only the HTTP call. The actual live
Meta API/webhook has not been exercised — you're the first real test.
"""

import os

import requests
from dotenv import load_dotenv

from connectors.base import PlatformAdapter, IncomingMessage
from connectors.meta_shared import verify_signature  # re-exported for webhooks/webhook_server.py
from database import webhook_inbox_store

load_dotenv()

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"
TEMPLATE_REQUIRED_ERROR_CODE = 131047  # Meta's code for "outside the 24h customer service window"

__all__ = ["WhatsAppAdapter", "verify_signature", "parse_webhook_payload"]


def _redact(text: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "[REDACTED]")
    return text


def parse_webhook_payload(payload: dict) -> list[dict]:
    """
    Extracts {"platform_user_id", "display_name", "text", "message_id",
    "timestamp"} dicts from a parsed WhatsApp Cloud API webhook body.
    Only type == "text" messages are handled — other types (images,
    documents, location, interactive replies, status updates) are
    skipped, not errors, matching Telegram's own text-only handling.

    display_name comes from the payload's own `contacts[].profile.name`
    (keyed by wa_id) when Meta includes it, falling back to a generic
    placeholder if it doesn't — the same "don't fake data you don't
    have" principle as history_analyzer's honest cold-start elsewhere
    in this project.
    """
    results = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts_by_wa_id = {
                c["wa_id"]: c.get("profile", {}).get("name", "")
                for c in value.get("contacts", [])
                if c.get("wa_id")
            }
            for msg in value.get("messages", []):
                if msg.get("type") != "text" or "text" not in msg:
                    continue
                sender = msg.get("from")
                if not sender:
                    continue
                results.append({
                    "platform_user_id": str(sender),
                    "display_name": contacts_by_wa_id.get(sender) or f"whatsapp_user_{sender}",
                    "text": msg["text"].get("body", ""),
                    "message_id": msg.get("id", ""),
                    "timestamp": str(msg.get("timestamp", "")),
                })
    return results


class WhatsAppAdapter(PlatformAdapter):
    def __init__(self):
        self._access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
        self._phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()

    @property
    def platform_name(self) -> str:
        return "whatsapp"

    def is_configured(self) -> bool:
        return bool(self._access_token and self._phone_number_id)

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
                "WhatsApp adapter is not configured — set WHATSAPP_ACCESS_TOKEN "
                "and WHATSAPP_PHONE_NUMBER_ID in .env first."
            )

        try:
            resp = requests.post(
                f"{GRAPH_API_BASE}/{self._phone_number_id}/messages",
                headers={"Authorization": f"Bearer {self._access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": platform_user_id,
                    "type": "text",
                    "text": {"body": text},
                },
                timeout=15,
            )
            data = resp.json()
            if resp.status_code >= 400:
                error = data.get("error", {})
                if error.get("code") == TEMPLATE_REQUIRED_ERROR_CODE:
                    raise RuntimeError(
                        "WhatsApp rejected this send: more than 24 hours have passed since this "
                        "contact last messaged you, so only a pre-approved template message can be "
                        "sent, not a free-form reply. (Meta error code 131047.)"
                    )
                raise RuntimeError(_redact(f"WhatsApp send failed ({resp.status_code}): {data}", self._access_token))
            return bool(data.get("messages"))
        except requests.exceptions.RequestException as e:
            raise RuntimeError(_redact(f"WhatsApp send request failed: {e}", self._access_token)) from e
