"""
scripts/approval_cli.py

Terminal version of spec section 19's Approval Center. The dashboard
has a page for this too — this CLI exists for quick checks without
opening a browser.

Phase 10 update: approving or editing a pending reply now actually
sends it via the real platform connector (agent/actions/action_dispatcher.py),
using the approval's contact_id. If the contact has no platform/
platform_id on record (e.g. it came from conversation import, not a
live connector), the send fails loudly rather than pretending to
succeed — the approval is still marked resolved, but you're told
plainly that nothing was actually sent.

Usage:
    python scripts/approval_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.security.approval_queue import list_pending, resolve_approval, always_allow, never_allow
from agent.actions.action_dispatcher import dispatch_send, DispatchError


def _try_send(item: dict, final_text: str) -> None:
    if item["contact_id"] is None:
        print("[!] This approval has no associated contact — nothing to send to.")
        return
    try:
        dispatch_send(item["contact_id"], final_text)
        print(f"Sent: \"{final_text}\"")
    except DispatchError as e:
        print(f"[!] Approved, but sending failed: {e}")


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
            _try_send(item, item["payload"].get("draft_text", ""))
        elif choice == "e":
            new_text = input("New text: ").strip()
            edited_payload = dict(item["payload"])
            edited_payload["draft_text"] = new_text
            resolve_approval(item["id"], "edited", edited_payload=edited_payload)
            _try_send(item, new_text)
        elif choice == "r":
            resolve_approval(item["id"], "rejected")
            print("Rejected. Nothing sent.")
        elif choice == "1":
            resolve_approval(item["id"], "approved")
            always_allow(item["action_type"])
            _try_send(item, item["payload"].get("draft_text", ""))
            print(f"'{item['action_type']}' is now set to AUTO going forward.")
        elif choice == "2":
            resolve_approval(item["id"], "rejected")
            never_allow(item["action_type"])
            print(f"Rejected. Nothing sent. '{item['action_type']}' is now set to NEVER going forward.")
        else:
            print("Skipped — still pending.")


if __name__ == "__main__":
    main()
