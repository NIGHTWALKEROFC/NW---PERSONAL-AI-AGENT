"""
database/task_store.py

Storage for the "task memory" layer from spec section 7. This is
storage only — the natural-language task planner that turns requests
like "watch this conversation and let me know if I need to respond"
into these rows is a later phase (spec section 14) and does not exist
yet. For now this just gives later phases somewhere to read/write
task state without needing another schema migration.
"""

import datetime

from database.db import get_connection

VALID_STATUSES = {"pending", "active", "completed", "failed", "expired", "cancelled"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def create_task(goal: str, trigger_condition: str | None = None, schedule: str | None = None, expires_at: str | None = None) -> int:
    conn = get_connection()
    now = _now()
    cur = conn.execute(
        "INSERT INTO task_memory (goal, trigger_condition, status, schedule, created_at, updated_at, expires_at) "
        "VALUES (?, ?, 'pending', ?, ?, ?, ?)",
        (goal, trigger_condition, schedule, now, now, expires_at),
    )
    conn.commit()
    return cur.lastrowid


def update_task_status(task_id: int, status: str) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}")
    conn = get_connection()
    cur = conn.execute(
        "UPDATE task_memory SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), task_id),
    )
    conn.commit()
    return cur.rowcount > 0


def list_tasks(status: str | None = None) -> list[dict]:
    conn = get_connection()
    if status is None:
        rows = conn.execute("SELECT * FROM task_memory ORDER BY created_at DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM task_memory WHERE status = ? ORDER BY created_at DESC", (status,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_task(task_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM task_memory WHERE id = ?", (task_id,))
    conn.commit()
    return cur.rowcount > 0
