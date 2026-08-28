"""
scripts/log_correction.py

Phase 5 (real reply generation) doesn't exist yet, so there's nowhere
automatic for corrections to come from. This script lets you feed the
correction-learning mechanism manually in the meantime — paste what an
AI draft might have said, then what you'd actually send instead — so
the pattern-tagging and confidence system can be tested and start
building signal ahead of Phase 5.

Usage:
    python scripts/log_correction.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
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

    print("Log a correction — this teaches the agent your real style.\n")
    original = input("AI's original draft: ").strip()
    edited = input("What you'd actually send: ").strip()

    if not original or not edited:
        print("Both fields are needed — nothing logged.")
        return

    try:
        result = log_correction(original, edited, model_name)
    except RuntimeError as e:
        print(f"[!] {e}")
        return

    print(f"\nPattern: {result['description']}")
    print(f"Tags: {result['tags']}")
    for tag, confidence in result["tag_confidences"].items():
        print(f"  {tag}: confidence {confidence}")
    if result["newly_promoted"]:
        print(f"\nPromoted to learned_patterns (seen {3}+ times now): {result['newly_promoted']}")


if __name__ == "__main__":
    main()
