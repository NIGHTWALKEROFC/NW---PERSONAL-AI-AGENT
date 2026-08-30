"""
database/contact_store.py

Per-contact memory layer. As of Phase 8, relationship_context and
contact_memories.content are encrypted at rest. The contact's `name`
is deliberately NOT encrypted — it's used in WHERE clauses for lookup
and dedup, and encrypting it would require weaker deterministic
encryption to keep that working. See database/crypto.py for exactly
what encryption here does and doesn't protect against.

If you have data from before Phase 8, run
scripts/encrypt_existing_data.py once to encrypt it in place.

Permissions per-contact are NOT handled here — that's Phase 8's
permission engine (agent/security/permission_engine.py), which is
global per action type, not yet per-contact. Storage only.
"""

import datetime

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def get_or_create_contact(name: str, platform: str | None = None, platform_id: str | None = None) -> int:
    conn = get_connection()
    row = conn.execute("SELECT id FROM contacts WHERE name = ?", (name,)).fetchone()
    if row:
        if platform_id is not None:
            conn.execute("UPDATE contacts SET platform_id = ? WHERE id = ?", (platform_id, row["id"]))
            conn.commit()
        return row["id"]

    now = _now()
    cur = conn.execute(
        "INSERT INTO contacts (name, platform, platform_id, relationship_context, created_at, updated_at) "
        "VALUES (?, ?, ?, NULL, ?, ?)",
        (name, platform, platform_id, now, now),
    )
    conn.commit()
    return cur.lastrowid


def get_contact_by_platform_id(platform: str, platform_id: str) -> dict | None:
    """Looks up a contact by their platform-specific ID (e.g. a Telegram chat ID) — used when an
    incoming message arrives and needs to be matched to an existing contact record."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM contacts WHERE platform = ? AND platform_id = ?", (platform, platform_id)
    ).fetchone()
    if row is None:
        return None
    contact = dict(row)
    contact["relationship_context"] = decrypt_text(contact["relationship_context"])
    return contact


def get_contact_by_name(name: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM contacts WHERE name = ?", (name,)).fetchone()
    if row is None:
        return None
    contact = dict(row)
    contact["relationship_context"] = decrypt_text(contact["relationship_context"])
    return contact


def list_contacts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM contacts ORDER BY updated_at DESC").fetchall()
    results = []
    for r in rows:
        c = dict(r)
        c["relationship_context"] = decrypt_text(c["relationship_context"])
        results.append(c)
    return results


def set_relationship_context(contact_id: int, context: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE contacts SET relationship_context = ?, updated_at = ? WHERE id = ?",
        (encrypt_text(context), _now(), contact_id),
    )
    conn.commit()


def add_contact_memory(contact_id: int, memory_type: str, content: str, confidence: float = 0.5) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO contact_memories (contact_id, memory_type, content, confidence, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (contact_id, memory_type, encrypt_text(content), confidence, _now()),
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
    results = []
    for r in rows:
        m = dict(r)
        m["content"] = decrypt_text(m["content"])
        results.append(m)
    return results


def set_conversation_state(contact_id: int, state: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM contact_memories WHERE contact_id = ? AND memory_type = 'conversation_state'",
        (contact_id,),
    )
    conn.execute(
        "INSERT INTO contact_memories (contact_id, memory_type, content, confidence, created_at) "
        "VALUES (?, 'conversation_state', ?, 1.0, ?)",
        (contact_id, encrypt_text(state), _now()),
    )
    conn.commit()


def get_conversation_state(contact_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT content FROM contact_memories WHERE contact_id = ? AND memory_type = 'conversation_state' "
        "ORDER BY created_at DESC LIMIT 1",
        (contact_id,),
    ).fetchone()
    return decrypt_text(row["content"]) if row else None


def delete_contact(contact_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM contact_memories WHERE contact_id = ?", (contact_id,))
    conn.execute("DELETE FROM conversation_messages WHERE contact_id = ?", (contact_id,))
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
