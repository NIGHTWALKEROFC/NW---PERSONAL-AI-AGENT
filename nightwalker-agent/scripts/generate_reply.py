"""
scripts/generate_reply.py

Feed in an incoming message (and optionally a contact name) and see
the full Phase 5 pipeline run: candidates generated, one selected,
quality-checked, with reasoning shown at every step.

Afterward, you're asked what you'd actually send instead. If it's
different from what the pipeline picked, it's automatically logged as
a correction (Phase 3's learning mechanism) — so testing this pipeline
naturally feeds the system real signal, instead of needing a separate
manual step via log_correction.py.

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

    print("\nRunning pipeline (generating candidates, selecting, quality-checking)...\n")
    result = generate_reply(incoming, contact_name=contact_name)

    print(f"--- Candidates ({len(result['all_candidates'])}) ---")
    for i, c in enumerate(result["all_candidates"]):
        marker = " <- selected" if i == result["selected_index"] else ""
        print(f"  [{i}] (temp {c['temperature']}): {c['text']}{marker}")

    print(f"\nSelection reasoning: {result['selection_reasoning']}")
    print(f"\nStatus: {result['status'].upper()}")
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
