"""
database/workflow_store.py

Storage for Phase 12 (teach-by-demonstration) workflows — spec section
13: record a manual demonstration once, then replay it as an editable,
previewable automation.

steps_json holds a JSON-encoded list of step dicts. Each step dict has
the same shape automation/desktop/actions.py's DesktopAction expects:
    {"action_type": ..., "params": {...}, "expected_state_description": ...}
plus an optional "label" (a human-readable note added during review,
e.g. "Click at (400, 620)") that's for human review only and is never
passed to DesktopAction.

steps_json is encrypted at rest exactly like other sensitive content
in this project (see database/crypto.py) — a recorded workflow can
contain typed text, which could be anything the user typed during the
demonstration, including something sensitive that wasn't fully
redacted during review.

Status lifecycle:
    draft    — just recorded/saved; not yet confirmed complete/correct.
               Still previewable via dry-run, but automation/desktop/
               workflow_executor.py refuses to run it for real.
    ready    — explicitly marked ready by the user (scripts/
               run_workflow_cli.py or a future dashboard action) —
               runnable for real, still subject to the exact same
               per-step permission/master-switch/verification chain
               as any other desktop action.
    disabled — explicitly turned off. Still previewable via dry-run
               (so you can see what it used to do), but never runnable
               for real until moved back to 'ready'.
"""

import datetime
import json

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text

VALID_STATUSES = {"draft", "ready", "disabled"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def create_workflow(name: str, steps: list[dict], status: str = "draft") -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}")
    conn = get_connection()
    now = _now()
    encrypted_steps = encrypt_text(json.dumps(steps, ensure_ascii=False))
    cur = conn.execute(
        "INSERT INTO workflows (name, steps_json, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, encrypted_steps, status, now, now),
    )
    conn.commit()
    return cur.lastrowid


def _decrypt_row(row) -> dict:
    row = dict(row)
    row["steps"] = json.loads(decrypt_text(row["steps_json"]))
    del row["steps_json"]
    return row


def get_workflow(workflow_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    return _decrypt_row(row) if row else None


def list_workflows(status: str | None = None) -> list[dict]:
    conn = get_connection()
    if status is None:
        rows = conn.execute("SELECT * FROM workflows ORDER BY updated_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM workflows WHERE status = ? ORDER BY updated_at DESC", (status,)
        ).fetchall()
    return [_decrypt_row(r) for r in rows]


def update_steps(workflow_id: int, steps: list[dict]) -> bool:
    conn = get_connection()
    encrypted_steps = encrypt_text(json.dumps(steps, ensure_ascii=False))
    cur = conn.execute(
        "UPDATE workflows SET steps_json = ?, updated_at = ? WHERE id = ?",
        (encrypted_steps, _now(), workflow_id),
    )
    conn.commit()
    return cur.rowcount > 0


def rename_workflow(workflow_id: int, name: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE workflows SET name = ?, updated_at = ? WHERE id = ?",
        (name, _now(), workflow_id),
    )
    conn.commit()
    return cur.rowcount > 0


def set_status(workflow_id: int, status: str) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}")
    conn = get_connection()
    cur = conn.execute(
        "UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), workflow_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_workflow(workflow_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
    conn.commit()
    return cur.rowcount > 0
