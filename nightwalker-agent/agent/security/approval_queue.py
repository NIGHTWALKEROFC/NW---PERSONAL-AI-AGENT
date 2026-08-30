"""
agent/security/approval_queue.py

The approval queue backing spec section 19's Approval Center:
    PENDING ACTION -> [ APPROVE ] [ EDIT ] [ REJECT ] [ ALWAYS ALLOW ] [ NEVER ALLOW ]

The payload (e.g. a drafted reply's text) is encrypted at rest, same
as everything else sensitive in this database — see database/crypto.py.

"Always allow" and "never allow" update the permission engine for that
action type going forward (AUTO or NEVER respectively) — so approving
the same kind of thing repeatedly can graduate it out of needing
manual approval each time, exactly as the spec's approval center
implies.
"""

import datetime
import json

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text
from agent.security.permission_engine import set_permission
from agent.security.security_events import log_event

VALID_DECISIONS = {"approved", "edited", "rejected"}


def create_approval(action_type: str, payload: dict, reasoning: str = "", contact_id: int | None = None) -> int:
    """
    payload: a dict with whatever detail is relevant (e.g. {"draft_text": "..."}) —
    stored as encrypted JSON.
    """
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    encrypted_payload = encrypt_text(json.dumps(payload, ensure_ascii=False))
    cur = conn.execute(
        "INSERT INTO pending_approvals (action_type, contact_id, payload, reasoning, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (action_type, contact_id, encrypted_payload, reasoning, now),
    )
    conn.commit()
    log_event("approval_created", f"action_type={action_type}, id={cur.lastrowid}")
    return cur.lastrowid


def _decrypt_row(row: dict) -> dict:
    row = dict(row)
    row["payload"] = json.loads(decrypt_text(row["payload"]))
    return row


def list_pending() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM pending_approvals WHERE status = 'pending' ORDER BY created_at ASC"
    ).fetchall()
    return [_decrypt_row(r) for r in rows]


def get_approval(approval_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
    return _decrypt_row(row) if row else None


def resolve_approval(approval_id: int, decision: str, edited_payload: dict | None = None) -> bool:
    """
    decision: 'approved', 'edited', or 'rejected'.
    edited_payload: required if decision == 'edited' — replaces the stored payload
    with what was actually approved, so the record reflects what really happened.
    """
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision '{decision}'. Must be one of: {sorted(VALID_DECISIONS)}")

    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"

    if decision == "edited" and edited_payload is not None:
        conn.execute(
            "UPDATE pending_approvals SET status = ?, payload = ?, resolved_at = ? WHERE id = ?",
            (decision, encrypt_text(json.dumps(edited_payload, ensure_ascii=False)), now, approval_id),
        )
    else:
        conn.execute(
            "UPDATE pending_approvals SET status = ?, resolved_at = ? WHERE id = ?",
            (decision, now, approval_id),
        )
    conn.commit()
    log_event("approval_resolved", f"id={approval_id}, decision={decision}")
    return True


def always_allow(action_type: str) -> None:
    """Sets this action type to AUTO going forward — future occurrences skip the approval queue."""
    set_permission(action_type, "AUTO")
    log_event("permission_changed", f"action_type={action_type}, new_level=AUTO (via always_allow)")


def never_allow(action_type: str) -> None:
    """Sets this action type to NEVER going forward — future occurrences are blocked outright."""
    set_permission(action_type, "NEVER")
    log_event("permission_changed", f"action_type={action_type}, new_level=NEVER (via never_allow)")
