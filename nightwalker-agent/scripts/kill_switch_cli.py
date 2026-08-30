"""
scripts/kill_switch_cli.py

Terminal control for the kill switch (agent/security/kill_switch.py).
See that file's docstring for exactly what this does and doesn't stop
— it's scoped honestly to what actually exists right now, not the
full spec section 20 vision.

Usage:
    python scripts/kill_switch_cli.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.security.kill_switch import activate, reactivate
from database.state_store import get_state, set_state, delete_state

# Stores the previous permission levels so reactivate can restore them —
# kept in agent_state under its own key, separate from the timing pause key.
KILL_SWITCH_STATE_KEY = "kill_switch_previous_levels"


def main():
    print("1) ACTIVATE kill switch (pause + disable outgoing replies)")
    print("2) Reactivate (resume + restore previous permission levels)")
    choice = input("Choice: ").strip()

    if choice == "1":
        result = activate()
        set_state(KILL_SWITCH_STATE_KEY, json.dumps(result["previous_levels"]))
        print("\nKill switch ACTIVATED.")
        print(f"Disabled: {result['disabled_actions']}")
        print("Not applicable yet (don't exist as systems):")
        for item in result["not_applicable"]:
            print(f"  - {item}")
    elif choice == "2":
        stored = get_state(KILL_SWITCH_STATE_KEY)
        previous_levels = json.loads(stored) if stored else {}
        reactivate(previous_levels)
        delete_state(KILL_SWITCH_STATE_KEY)
        print("\nReactivated. Timing resumed, previous permission levels restored.")
    else:
        print("No changes made.")


if __name__ == "__main__":
    main()
