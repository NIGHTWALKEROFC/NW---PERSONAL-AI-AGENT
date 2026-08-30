"""
database/memory_store.py

Short-term, long-term, and temporary memory layers. As of Phase 8, the
`content` field in every table here is encrypted at rest (roles,
categories, timestamps, and memory_layer labels stay plaintext since
they're needed for filtering/querying — see database/crypto.py for
exactly what this protects against and what it doesn't).

If you have data from before Phase 8, run
scripts/encrypt_existing_data.py once to encrypt it in place.
"""

import datetime

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _decrypt_message_row(row: dict) -> dict:
    row = dict(row)
    row["content"] = decrypt_text(row["content"])
    return row


# ---------------------------------------------------------------------------
# General-purpose message logging
# ---------------------------------------------------------------------------

def log_message(role: str, content: str, contact_id: int | None = None,
                 memory_layer: str = "short_term", created_at: str | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO conversation_messages (contact_id, role, content, memory_layer, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (contact_id, role, encrypt_text(content), memory_layer, created_at or _now()),
    )
    conn.commit()
    return cur.lastrowid


def get_messages_for_contact(contact_id: int, memory_layer: str | None = None) -> list[dict]:
    conn = get_connection()
    if memory_layer is None:
        rows = conn.execute(
            "SELECT * FROM conversation_messages WHERE contact_id = ? ORDER BY created_at ASC",
            (contact_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM conversation_messages WHERE contact_id = ? AND memory_layer = ? ORDER BY created_at ASC",
            (contact_id, memory_layer),
        ).fetchall()
    return [_decrypt_message_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Short-term memory (recent conversation)
# ---------------------------------------------------------------------------

def add_short_term_message(role: str, content: str, contact_id: int | None = None) -> int:
    return log_message(role, content, contact_id=contact_id, memory_layer="short_term")


def get_recent_short_term(limit: int = 20, contact_id: int | None = None) -> list[dict]:
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
    return [_decrypt_message_row(r) for r in reversed(rows)]


def clear_short_term(contact_id: int | None = None) -> int:
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
        (category, encrypt_text(content), importance, source, _now()),
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
    return [_decrypt_message_row(r) for r in rows]


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
        (encrypt_text(content), now.isoformat() + "Z", expires_at),
    )
    conn.commit()
    return cur.lastrowid


def get_active_temporary_memory() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM temporary_memory WHERE expires_at > ? ORDER BY id DESC", (_now(),)
    ).fetchall()
    return [_decrypt_message_row(r) for r in rows]


def purge_expired_temporary_memory() -> int:
    conn = get_connection()
    cur = conn.execute("DELETE FROM temporary_memory WHERE expires_at <= ?", (_now(),))
    conn.commit()
    return cur.rowcount
