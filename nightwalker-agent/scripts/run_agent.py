"""
scripts/run_agent.py

Run this to chat with the Phase 1 agent in your terminal.

Usage:
    python scripts/run_agent.py

Type 'reset' to clear conversation history.
Type 'exit' or 'quit' to stop.
"""

import sys
import os

# Allow running this script directly from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.core import Agent
from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model


def main():
    model_name = get_active_model()
    print(f"NightWalker Agent — Phase 1 (model: {model_name})")

    client = ModelClient(model_name)
    if not client.is_available():
        print(
            "\n[!] Cannot reach Ollama. Make sure it's running, then try again.\n"
            "    Check with: ollama list\n"
        )
        return

    agent = Agent()
    print("Ready. Type 'exit' to quit, 'reset' to clear history.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Exiting.")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("[history cleared]\n")
            continue

        reply = agent.send(user_input)
        print(f"agent> {reply}\n")


if __name__ == "__main__":
    main()
