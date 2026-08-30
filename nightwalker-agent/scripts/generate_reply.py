"""
scripts/generate_reply.py

Feed in an incoming message (and optionally a contact name) and see
the full pipeline run: candidates generated, one selected,
quality-checked, and (Phase 8) permission-checked.

If the permission level for sending a reply is ASK, this now creates
a real approval request instead of just showing you the result —
check it with the dashboard's Approval Center or scripts/approval_cli.py.

Afterward, you're asked what you'd actually send instead. If it's
different from what the pipeline picked, it's logged as a correction.

Usage:
    python scripts/generate_reply.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
from agent.reply.pipeline import generate_reply
from agent.personality.correction_learning import log_correction


def main():
    model_name = get_active_model()
    client = ModelClient(model_name)
    if not client.is_available():
        print(
            "\n[!] Cannot reach Ollama. Make sure it's running, then try again.\n"
            "    Check with: ollama list\n"
        )
        return

    print("Reply generation pipeline test\n")
    incoming = input("Incoming message to reply to: ").strip()
    if not incoming:
        print("No message given — nothing to do.")
        return

    contact_name = input("Contact name (press enter to skip): ").strip() or None

    print("\nRunning pipeline (generating candidates, selecting, quality-checking, permission-checking)...\n")
    result = generate_reply(incoming, contact_name=contact_name)

    print(f"--- Candidates ({len(result['all_candidates'])}) ---")
    for i, c in enumerate(result["all_candidates"]):
        marker = " <- selected" if i == result["selected_index"] else ""
        print(f"  [{i}] (temp {c['temperature']}): {c['text']}{marker}")

    print(f"\nSelection reasoning: {result['selection_reasoning']}")
    print(f"\nStatus: {result['status'].upper()}")
    if result.get("permission_level"):
        print(f"Permission level for sending: {result['permission_level']}")
    if result["status"] == "pending_approval":
        print(f"An approval request was created (id: {result['approval_id']}) — review it in the dashboard's Approval Center.")
    if result["status"] == "blocked":
        print("This reply was blocked — sending is currently DISABLED or NEVER allowed.")
    if result["quality"]["concerns"]:
        print("Concerns raised:")
        for concern in result["quality"]["concerns"]:
            print(f"  - {concern}")

    print(f"\nFinal draft:\n  {result['selected_text']}\n")

    actual = input("What would you actually send instead? (press enter to accept as-is): ").strip()
    if actual and actual != result["selected_text"]:
        print("\nLogging this as a correction...")
        correction_result = log_correction(result["selected_text"], actual, model_name)
        print(f"  Pattern: {correction_result['description']}")
        print(f"  Tags: {correction_result['tags']}")
        if correction_result["newly_promoted"]:
            print(f"  Newly promoted to learned_patterns: {correction_result['newly_promoted']}")
    else:
        print("\nAccepted as-is — nothing logged (no difference to learn from).")


if __name__ == "__main__":
    main()
