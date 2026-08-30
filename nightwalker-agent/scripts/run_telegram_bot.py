"""
scripts/run_telegram_bot.py

The actual "read message -> decide -> maybe send" loop for the
Telegram connector. This is the culmination of Phases 1-9: every
incoming message goes through the SAME reply pipeline used everywhere
else in this project (personality-aware context, candidate generation,
quality checks, permission checks, timing checks) before anything is
ever sent.

What happens to each incoming message, based on the pipeline's status:

    ready             -> scheduled to actually send, after the timing
                         engine's suggested delay (a real send — this
                         is not a preview)
    pending_approval  -> nothing is sent; the approval already exists
                         in the queue (dashboard: /approvals)
    blocked           -> permission is DISABLED/NEVER; not sent, logged
    timing_blocked    -> paused or within sleep hours; not sent, logged
    needs_review      -> failed a quality/safety check; not sent, logged

Stopping this script (Ctrl+C) stops the bot. The security kill switch
and manual pause (both already enforced INSIDE the pipeline via the
timing engine and permission engine) work exactly the same way here as
everywhere else — there's no separate on/off switch to remember for
this connector specifically.

Usage:
    python scripts/run_telegram_bot.py
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connectors.telegram.telegram_adapter import TelegramAdapter
from database.contact_store import get_or_create_contact
from database.memory_store import log_message
from agent.reply.pipeline import generate_reply
from agent.actions.action_dispatcher import dispatch_send, DispatchError
from agent.security.security_events import log_event

POLL_INTERVAL_SECONDS = 2  # gap between polling calls when there's nothing new


def handle_incoming(adapter: TelegramAdapter, incoming) -> None:
    contact_id = get_or_create_contact(
        incoming.display_name, platform="telegram", platform_id=incoming.platform_user_id
    )

    log_message(incoming.display_name, incoming.text, contact_id=contact_id, memory_layer="short_term")
    print(f"\n[incoming] {incoming.display_name}: {incoming.text}")

    result = generate_reply(incoming.text, contact_name=incoming.display_name)
    print(f"[pipeline] status={result['status']}")

    if result["status"] == "ready":
        delay = result["timing"]["delay_seconds"] if result["timing"] else 0
        text = result["selected_text"]
        print(f"[scheduling] will send in {delay}s: \"{text}\"")

        def _send():
            try:
                dispatch_send(contact_id, text)
                print(f"[sent] to {incoming.display_name}: \"{text}\"")
            except DispatchError as e:
                print(f"[send failed] {e}")
                log_event("send_failed", str(e))

        threading.Timer(delay, _send).start()

    elif result["status"] == "pending_approval":
        print(f"[waiting] approval id {result['approval_id']} created — check the dashboard's Approval Center.")

    elif result["status"] == "blocked":
        print(f"[blocked] permission level is {result['permission_level']} — not sending.")

    elif result["status"] == "timing_blocked":
        print(f"[waiting] {result['timing']['reason']}")

    else:  # needs_review
        print(f"[needs review] concerns: {result['quality']['concerns']}")


def main():
    adapter = TelegramAdapter()

    if not adapter.is_configured():
        print(
            "\n[!] TELEGRAM_BOT_TOKEN is not set in .env.\n"
            "    Create a bot via @BotFather on Telegram, then add the token to .env.\n"
        )
        return

    print("NightWalker Telegram connector running. Press Ctrl+C to stop.\n")
    log_event("telegram_connector_started", "")

    try:
        while True:
            try:
                messages = adapter.fetch_incoming_messages()
            except RuntimeError as e:
                print(f"[error] {e}")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            for incoming in messages:
                handle_incoming(adapter, incoming)

            if not messages:
                time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopping.")
        log_event("telegram_connector_stopped", "")


if __name__ == "__main__":
    main()
