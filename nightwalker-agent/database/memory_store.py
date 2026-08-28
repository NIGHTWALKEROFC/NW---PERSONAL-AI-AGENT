"""
database/memory_store.py

Three of the six memory layers from the spec:

- short-term: recent conversation turns, stored as rows in
  conversation_messages with memory_layer='short_term'
- long-term: important information that should persist, in its own
  table so it's never accidentally pruned the way short-term is
- temporary: information with an explicit expiry, auto-purged

Behavioral memory (patterns about how the person communicates) is
intentionally NOT duplicated here — that's the personality profile
(agent/personality/profile_store.py), now also backed by this same
database. Splitting it into a second copy would just create two
sources of truth that drift apart.

Contact memory and task memory live in their own files
(contact_store.py, task_store.py) since they have distinct shapes.
"""

import datetime

from database.db import get_connection


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# Short-term memory (recent conversation)
# ---------------------------------------------------------------------------

def add_short_term_message(role: str, content: str, contact_id: int | None = None) -> int:
    """
    role: 'me', 'agent', or a contact's name — whatever the caller uses
    consistently. Returns the new row's id.
    """
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO conversation_messages (contact_id, role, content, memory_layer, created_at) "
        "VALUES (?, ?, ?, 'short_term', ?)",
        (contact_id, role, content, _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_recent_short_term(limit: int = 20, contact_id: int | None = None) -> list[dict]:
    """Returns the most recent messages, oldest first (ready to feed into a chat history list)."""
    conn = get_connection()
    if contact_id is None:
        rows = conn.execute(
            "SELECT * FROM conversation_messages WHERE memory_layer = 'short_term' AND contact_id IS NULL "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversation_messages WHERE memory_layer = 'short_term' AND contact_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (contact_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def clear_short_term(contact_id: int | None = None) -> int:
    """Deletes short-term messages. Returns the number of rows deleted."""
    conn = get_connection()
    if contact_id is None:
        cur = conn.execute("DELETE FROM conversation_messages WHERE memory_layer = 'short_term' AND contact_id IS NULL")
    else:
        cur = conn.execute("DELETE FROM conversation_messages WHERE memory_layer = 'short_term' AND contact_id = ?", (contact_id,))
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Long-term memory
# ---------------------------------------------------------------------------

def add_long_term_memory(content: str, category: str = "general", importance: float = 0.5, source: str = "manual") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO long_term_memory (category, content, importance, source, created_at) VALUES (?, ?, ?, ?, ?)",
        (category, content, importance, source, _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_long_term_memory(category: str | None = None) -> list[dict]:
    conn = get_connection()
    if category is None:
        rows = conn.execute("SELECT * FROM long_term_memory ORDER BY importance DESC, id DESC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM long_term_memory WHERE category = ? ORDER BY importance DESC, id DESC", (category,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_long_term_memory(entry_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM long_term_memory WHERE id = ?", (entry_id,))
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Temporary memory (auto-expiring)
# ---------------------------------------------------------------------------

def add_temporary_memory(content: str, ttl_seconds: int) -> int:
    now = datetime.datetime.utcnow()
    expires_at = (now + datetime.timedelta(seconds=ttl_seconds)).isoformat() + "Z"
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO temporary_memory (content, created_at, expires_at) VALUES (?, ?, ?)",
        (content, now.isoformat() + "Z", expires_at),
    )
    conn.commit()
    return cur.lastrowid


def get_active_temporary_memory() -> list[dict]:
    """Returns only non-expired entries. Does not delete expired ones — call purge_expired_temporary_memory() for that."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM temporary_memory WHERE expires_at > ? ORDER BY id DESC", (_now(),)
    ).fetchall()
    return [dict(r) for r in rows]


def purge_expired_temporary_memory() -> int:
    """Deletes expired entries. Returns the number removed."""
    conn = get_connection()
    cur = conn.execute("DELETE FROM temporary_memory WHERE expires_at <= ?", (_now(),))
    conn.commit()
    return cur.rowcount
