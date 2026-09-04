"""
scripts/run_telegram_bot.py

The Telegram connector's runner. This is now a thin wrapper around
agent/actions/connector_runner.py's shared polling loop (extracted in
Phase 13 when Instagram/WhatsApp made the duplication obvious) — the
actual "read message -> decide -> maybe send" logic, and the honest
breakdown of what each pipeline status means, live there now, and are
identical for every platform. Nothing about how Telegram itself is
polled (TelegramAdapter.fetch_incoming_messages() via getUpdates) has
changed from Phase 10.

Usage:
    python scripts/run_telegram_bot.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from connectors.telegram.telegram_adapter import TelegramAdapter
from agent.actions.connector_runner import run_connector_loop

POLL_INTERVAL_SECONDS = 2  # gap between polling calls when there's nothing new


def main():
    adapter = TelegramAdapter()

    if not adapter.is_configured():
        print(
            "\n[!] TELEGRAM_BOT_TOKEN is not set in .env.\n"
            "    Create a bot via @BotFather on Telegram, then add the token to .env.\n"
        )
        return

    run_connector_loop(adapter, poll_interval_seconds=POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
