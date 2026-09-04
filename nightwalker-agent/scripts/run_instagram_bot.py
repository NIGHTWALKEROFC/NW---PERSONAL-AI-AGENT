"""
scripts/run_instagram_bot.py

The Instagram connector's runner. Uses the same shared polling loop as
every other platform (agent/actions/connector_runner.py) — see that
file's docstring for what happens to each incoming message.

What's different for Instagram: adapter.fetch_incoming_messages()
drains a local database queue fed by webhooks/webhook_server.py rather
than polling Meta directly (see connectors/instagram/instagram_adapter.py's
docstring for why), so this script does NOT talk to the network at
all. You need scripts/run_webhook_server.py running (and reachable by
Meta) at the same time as this one for any messages to ever arrive.

Usage:
    python scripts/run_instagram_bot.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connectors.instagram.instagram_adapter import InstagramAdapter
from agent.actions.connector_runner import run_connector_loop

POLL_INTERVAL_SECONDS = 1  # polling a local table, not Meta's API — a short interval costs nothing


def main():
    adapter = InstagramAdapter()

    if not adapter.is_configured():
        print(
            "\n[!] Instagram isn't configured — set INSTAGRAM_ACCESS_TOKEN and\n"
            "    INSTAGRAM_SENDER_ID in .env. See connectors/instagram/instagram_adapter.py\n"
            "    for full setup steps.\n"
        )
        return

    print("[reminder] scripts/run_webhook_server.py must also be running (and reachable")
    print("           by Meta) for any messages to arrive here.\n")
    run_connector_loop(adapter, poll_interval_seconds=POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
