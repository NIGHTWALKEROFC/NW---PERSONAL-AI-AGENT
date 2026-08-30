"""
database/state_store.py

Generic key-value storage for simple agent state that needs to persist
across restarts but doesn't warrant its own table — e.g. manual pause
status (Phase 6). Kept deliberately generic so Phase 8's kill switch
can reuse this same table instead of needing another one.
"""

import datetime

from database.db import get_connection


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def set_state(key: str, value: str) -> None:
    conn = get_connection()
    now = _now()
    conn.execute(
        "INSERT INTO agent_state (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, now),
    )
    conn.commit()


def get_state(key: str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def delete_state(key: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM agent_state WHERE key = ?", (key,))
    conn.commit()
