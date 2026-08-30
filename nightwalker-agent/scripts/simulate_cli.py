"""
scripts/simulate_cli.py

Run the full decision chain as a dry run — no real approval is
created, nothing is written to memory. Shows every stage of the
pipeline so you can see exactly why a given outcome would happen.

Optionally lets you temporarily override the permission level or pause
state for just this one simulation — the original value is always
restored afterward, whether the simulation succeeds or fails, so this
never leaves your real settings changed.

Usage:
    python scripts/simulate_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
from agent.simulation.simulator import simulate_incoming_message
from agent.security.permission_engine import get_permission, set_permission, VALID_LEVELS
from agent.timing.pause_control import is_paused, pause_indefinitely, resume


def main():
    model_name = get_active_model()
    client = ModelClient(model_name)
    if not client.is_available():
        print(
            "\n[!] Cannot reach Ollama. Make sure it's running, then try again.\n"
            "    Check with: ollama list\n"
        )
        return

    print("Simulation mode — nothing here creates a real approval or writes to memory.\n")
    incoming = input("Incoming message to simulate a reply to: ").strip()
    if not incoming:
        print("No message given — nothing to do.")
        return

    contact_name = input("Contact name (press enter to skip): ").strip() or None

    override_permission = input(
        f"\nTemporarily override the send_normal_reply permission for this test? "
        f"Current: {get_permission('send_normal_reply')} (press enter to skip, or type AUTO/ASK/SUGGEST/DISABLED/NEVER): "
    ).strip().upper()

    override_pause = input(
        "Temporarily simulate the agent being paused for this test? (y/N): "
    ).strip().lower() == "y"

    # Save real state, apply overrides, and guarantee restoration no matter what happens.
    original_permission = get_permission("send_normal_reply")
    original_paused, _ = is_paused()

    try:
        if override_permission and override_permission in VALID_LEVELS:
            set_permission("send_normal_reply", override_permission)
            print(f"(Temporarily set send_normal_reply to {override_permission} for this test)")
        elif override_permission:
            print(f"'{override_permission}' isn't a valid level — ignoring, using current setting.")

        if override_pause and not original_paused:
            pause_indefinitely()
            print("(Temporarily paused for this test)")

        print("\nRunning simulation...\n")
        result = simulate_incoming_message(incoming, contact_name=contact_name)

        print("--- Stage-by-stage trace ---")
        for step in result["stage_trace"]:
            print(f"  [{step['stage']}] {step['detail']}")

        print(f"\n--- Final verdict: {result['final_status'].upper()} ---")
        print(f"Selected text: {result['selected_text']}")
        if result["permission_level"]:
            print(f"Permission level used: {result['permission_level']}")
        if result["timing"]:
            print(f"Timing: allowed={result['timing']['allowed']}, delay={result['timing'].get('delay_seconds')}s, reason={result['timing']['reason']}")
        if result["would_be_approval_payload"]:
            print(f"Would-be approval payload: {result['would_be_approval_payload']}")

    finally:
        # Always restore, even if something above raised an exception.
        if override_permission and override_permission in VALID_LEVELS:
            set_permission("send_normal_reply", original_permission)
        if override_pause and not original_paused:
            resume()
        print("\n(Any temporary overrides have been restored to their original values.)")


if __name__ == "__main__":
    main()
