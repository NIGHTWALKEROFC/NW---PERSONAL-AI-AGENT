"""
scripts/approval_cli.py

Terminal version of spec section 19's Approval Center. The dashboard
has a page for this too (Phase 8 dashboard update) — this CLI exists
for quick checks without opening a browser.

Usage:
    python scripts/approval_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.security.approval_queue import list_pending, resolve_approval, always_allow, never_allow


def main():
    pending = list_pending()

    if not pending:
        print("No pending approvals.")
        return

    for item in pending:
        print("\n" + "=" * 50)
        print(f"PENDING ACTION [{item['id']}]")
        print(f"Action type: {item['action_type']}")
        print(f"Reasoning: {item['reasoning']}")
        print(f"Payload:")
        for key, value in item["payload"].items():
            print(f"  {key}: {value}")

        print("\n[A]pprove  [E]dit  [R]eject  [1] Always allow this action type  [2] Never allow this action type  [S]kip")
        choice = input("Choice: ").strip().lower()

        if choice == "a":
            resolve_approval(item["id"], "approved")
            print("Approved.")
        elif choice == "e":
            new_text = input("New text: ").strip()
            edited_payload = dict(item["payload"])
            edited_payload["draft_text"] = new_text
            resolve_approval(item["id"], "edited", edited_payload=edited_payload)
            print("Approved with edits.")
        elif choice == "r":
            resolve_approval(item["id"], "rejected")
            print("Rejected.")
        elif choice == "1":
            resolve_approval(item["id"], "approved")
            always_allow(item["action_type"])
            print(f"Approved, and '{item['action_type']}' is now set to AUTO going forward.")
        elif choice == "2":
            resolve_approval(item["id"], "rejected")
            never_allow(item["action_type"])
            print(f"Rejected, and '{item['action_type']}' is now set to NEVER going forward.")
        else:
            print("Skipped — still pending.")


if __name__ == "__main__":
    main()
