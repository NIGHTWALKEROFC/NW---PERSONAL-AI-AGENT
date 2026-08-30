"""
agent/security/security_events.py

A lightweight audit trail — not the full "privacy-conscious logging"
system from spec section 25 (that would cover every action across the
whole agent; this is scoped specifically to security-relevant events:
permission changes, approval decisions, the kill switch, and data
wipes). Feeds the Security dashboard page's "recent security events".
"""

import datetime

from database.db import get_connection


def log_event(event_type: str, detail: str = "") -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO security_events (event_type, detail, created_at) VALUES (?, ?, ?)",
        (event_type, detail, datetime.datetime.utcnow().isoformat() + "Z"),
    )
    conn.commit()


def get_recent_events(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM security_events ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]
