"""
database/contact_store.py

Per-contact memory layer, matching spec section 6's conversation
profile shape:

    contact
    ├── communication_history   (conversation_messages, filtered by contact_id)
    ├── relationship_context    (contacts.relationship_context)
    ├── common_topics           (contact_memories, memory_type='common_topic')
    ├── communication_style     (contact_memories, memory_type='communication_style')
    ├── important_memories      (contact_memories, memory_type='important_memory')
    ├── response_patterns       (contact_memories, memory_type='response_pattern')
    └── current_conversation_state (contact_memories, memory_type='conversation_state' — usually one row, overwritten)

Permissions per-contact are NOT handled here — that belongs to the
Phase 8 permission engine, which doesn't exist yet. This file is
storage only.
"""

import datetime

from database.db import get_connection


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def get_or_create_contact(name: str, platform: str | None = None) -> int:
    """Returns the contact's id, creating a new row if this name hasn't been seen before."""
    conn = get_connection()
    row = conn.execute("SELECT id FROM contacts WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]

    now = _now()
    cur = conn.execute(
        "INSERT INTO contacts (name, platform, relationship_context, created_at, updated_at) "
        "VALUES (?, ?, NULL, ?, ?)",
        (name, platform, now, now),
    )
    conn.commit()
    return cur.lastrowid


def get_contact_by_name(name: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM contacts WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def list_contacts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM contacts ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def set_relationship_context(contact_id: int, context: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE contacts SET relationship_context = ?, updated_at = ? WHERE id = ?",
        (context, _now(), contact_id),
    )
    conn.commit()


def add_contact_memory(contact_id: int, memory_type: str, content: str, confidence: float = 0.5) -> int:
    """
    memory_type: 'common_topic', 'communication_style', 'important_memory',
    'response_pattern', 'conversation_state', or any other label the caller
    finds useful — this is intentionally not a strict enum yet.
    """
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO contact_memories (contact_id, memory_type, content, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (contact_id, memory_type, content, confidence, _now()),
    )
    conn.commit()
    conn.execute("UPDATE contacts SET updated_at = ? WHERE id = ?", (_now(), contact_id))
    conn.commit()
    return cur.lastrowid


def get_contact_memories(contact_id: int, memory_type: str | None = None) -> list[dict]:
    conn = get_connection()
    if memory_type is None:
        rows = conn.execute(
            "SELECT * FROM contact_memories WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM contact_memories WHERE contact_id = ? AND memory_type = ? ORDER BY created_at DESC",
            (contact_id, memory_type),
        ).fetchall()
    return [dict(r) for r in rows]


def set_conversation_state(contact_id: int, state: str) -> None:
    """
    Conversation state is a single current value, not a growing log —
    this deletes prior state rows for the contact and writes one fresh row.
    """
    conn = get_connection()
    conn.execute(
        "DELETE FROM contact_memories WHERE contact_id = ? AND memory_type = 'conversation_state'",
        (contact_id,),
    )
    conn.execute(
        "INSERT INTO contact_memories (contact_id, memory_type, content, confidence, created_at) "
        "VALUES (?, 'conversation_state', ?, 1.0, ?)",
        (contact_id, state, _now()),
    )
    conn.commit()


def get_conversation_state(contact_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT content FROM contact_memories WHERE contact_id = ? AND memory_type = 'conversation_state' "
        "ORDER BY created_at DESC LIMIT 1",
        (contact_id,),
    ).fetchone()
    return row["content"] if row else None


def delete_contact(contact_id: int) -> None:
    """Removes a contact and all their memories/messages. Deliberate, not automatic."""
    conn = get_connection()
    conn.execute("DELETE FROM contact_memories WHERE contact_id = ?", (contact_id,))
    conn.execute("DELETE FROM conversation_messages WHERE contact_id = ?", (contact_id,))
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
