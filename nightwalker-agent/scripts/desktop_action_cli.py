"""
scripts/desktop_action_cli.py

Test desktop automation actions here BEFORE trusting the dashboard or
any automated workflow with them.

*** READ THIS FIRST ***
The screenshot/click/type/window functions this calls have NOT been
tested against a real display — there is no GUI in the environment
this project was built in. Only the surrounding safety logic
(permissions, master switch, verification gating, failure handling)
has been tested. Start with dry-run mode. When you're ready to test a
real action, use something with zero consequences if it goes wrong —
Notepad is the standard choice — before pointing this at anything that
matters.

Usage:
    python scripts/desktop_action_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from automation.desktop.actions import DesktopAction, VALID_ACTION_TYPES
from automation.desktop.safety_executor import execute_action
from automation.desktop.master_switch import is_enabled, enable, disable
from automation.desktop.availability import check_all


def main():
    print("=" * 60)
    print("DESKTOP AUTOMATION TEST CLI")
    print("The click/type/screenshot code has NOT been tested by the")
    print("developer against a real display. You are the first real test.")
    print("=" * 60)

    availability = check_all()
    print(f"\npyautogui available: {availability['pyautogui']['available']}")
    if not availability["pyautogui"]["available"]:
        print(f"  ({availability['pyautogui']['error']})")
    print(f"pygetwindow available: {availability['pygetwindow']['available']}")
    if not availability["pygetwindow"]["available"]:
        print(f"  ({availability['pygetwindow']['error']})")

    print(f"\nMaster switch (required for real, non-dry-run actions): {'ON' if is_enabled() else 'OFF'}")

    print(f"\nAction types: {sorted(VALID_ACTION_TYPES)}")
    action_type = input("Action type: ").strip()
    if action_type not in VALID_ACTION_TYPES:
        print("Not a valid action type.")
        return

    params = {}
    if action_type == "open_app":
        params["name_or_path"] = input("App name or path: ").strip()
    elif action_type == "click":
        params["x"] = int(input("X coordinate: ").strip())
        params["y"] = int(input("Y coordinate: ").strip())
    elif action_type == "type_text":
        params["text"] = input("Text to type: ").strip()

    expected_state = ""
    if action_type in ("click", "type_text"):
        expected_state = input("Describe what the screen should look like right now: ").strip()

    try:
        action = DesktopAction(action_type=action_type, params=params, expected_state_description=expected_state)
    except ValueError as e:
        print(f"[!] {e}")
        return

    dry_run_input = input("\nDry run (recommended)? [Y/n]: ").strip().lower()
    dry_run = dry_run_input != "n"

    if not dry_run:
        confirm = input(
            "\nThis will attempt a REAL action on your machine using code that has not been "
            "tested against a real display. Type 'I understand' to proceed: "
        ).strip()
        if confirm != "I understand":
            print("Cancelled.")
            return

    print("\nRunning...\n")
    result = execute_action(action, dry_run=dry_run)

    print("--- Trace ---")
    for step in result["trace"]:
        print(f"  {step}")

    print(f"\n--- Result: {result['status'].upper()} ---")
    if result.get("reason"):
        print(f"Reason: {result['reason']}")
    if result.get("result"):
        print(f"Result detail: {result['result']}")
    if result.get("approval_id"):
        print(f"Approval id: {result['approval_id']} — check the dashboard's Approval Center.")


if __name__ == "__main__":
    main()
