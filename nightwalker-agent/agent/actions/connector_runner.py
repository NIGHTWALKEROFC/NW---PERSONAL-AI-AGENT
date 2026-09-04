"""
agent/actions/connector_runner.py

The shared "read message -> decide -> maybe send" polling loop used by
every platform connector's runner script (scripts/run_telegram_bot.py,
scripts/run_instagram_bot.py, scripts/run_whatsapp_bot.py). Extracted
in Phase 13 when adding a second and third platform made the
duplication that used to live only in run_telegram_bot.py obvious —
this is a refactor of Phase 10's existing behavior, not new behavior;
Telegram's runner is functionally unchanged, it just calls this
instead of containing its own copy of the loop.

What happens to each incoming message, based on the pipeline's status,
is identical across every platform:

    ready             -> scheduled to actually send, after the timing
                         engine's suggested delay (a real send — this
                         is not a preview)
    pending_approval  -> nothing is sent; the approval already exists
                         in the queue (dashboard: /approvals)
    blocked           -> permission is DISABLED/NEVER; not sent, logged
    timing_blocked    -> paused or within sleep hours; not sent, logged
    needs_review      -> failed a quality/safety check; not sent, logged

The security kill switch and manual pause, already enforced INSIDE the
pipeline via the timing engine and permission engine, work exactly the
same way for every platform — there is no separate on/off switch to
remember per platform, and nothing here duplicates any of that logic.
"""

import time
import threading

from database.contact_store import get_or_create_contact
from database.memory_store import log_message
from agent.reply.pipeline import generate_reply
from agent.actions.action_dispatcher import dispatch_send, DispatchError
from agent.security.security_events import log_event


def handle_incoming(adapter, incoming) -> None:
    contact_id = get_or_create_contact(
        incoming.display_name, platform=adapter.platform_name, platform_id=incoming.platform_user_id
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


def run_connector_loop(adapter, poll_interval_seconds: float = 2) -> None:
    """
    Runs forever (until Ctrl+C), polling adapter.fetch_incoming_messages()
    and handling whatever comes back. Works identically whether the
    adapter's fetch is a real network poll (Telegram) or a local
    database drain (Instagram/WhatsApp, fed by webhooks/webhook_server.py)
    — this loop doesn't need to know or care which.
    """
    print(f"NightWalker {adapter.platform_name.title()} connector running. Press Ctrl+C to stop.\n")
    log_event(f"{adapter.platform_name}_connector_started", "")

    try:
        while True:
            try:
                messages = adapter.fetch_incoming_messages()
            except RuntimeError as e:
                print(f"[error] {e}")
                time.sleep(poll_interval_seconds)
                continue

            for incoming in messages:
                handle_incoming(adapter, incoming)

            if not messages:
                time.sleep(poll_interval_seconds)

    except KeyboardInterrupt:
        print("\nStopping.")
        log_event(f"{adapter.platform_name}_connector_stopped", "")
