"""
agent/personality/sensitive_store.py

Sensitive information (health mentions, financial details, identity
info, relationship/family conflict, anything in that category) is kept
in its own table — separate from the personality profile — never
merged in, never sent back into prompts unless a future phase
explicitly needs it with your permission.

*** SECURITY STATUS: NOT YET ENCRYPTED ***
This now lives in database/nightwalker.db alongside everything else,
but the database file itself is still plain SQLite, not encrypted.
Encryption at rest is planned for the Phase 8 security architecture
and has NOT been implemented. Until then, treat this data exactly like
an unencrypted password file: local-only, gitignored (already
handled), and not something to back up to any cloud service casually.

Entries store a short category + neutral flag, not necessarily full
verbatim detail — see conversation_analyzer.py for how these get
generated.

If you have an existing database/sensitive_profile.json from before
this phase, run scripts/migrate_json_to_sqlite.py once to bring it
into the database — it is not read automatically.
"""

import datetime

from database.db import get_connection


def append_entries(flags: list[str], source_label: str) -> None:
    """
    flags: short neutral descriptions, e.g. "mentioned a financial stress topic"
    source_label: where this came from, e.g. "conversation_import:whatsapp_export_2026.json"
    """
    if not flags:
        return
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conn.executemany(
        "INSERT INTO sensitive_entries (flag, source, added_at) VALUES (?, ?, ?)",
        [(flag, source_label, now) for flag in flags],
    )
    conn.commit()


def list_entries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sensitive_entries ORDER BY added_at DESC").fetchall()
    return [dict(r) for r in rows]


def clear_all() -> None:
    """Explicit, deliberate wipe — should only ever be called from a direct user action."""
    conn = get_connection()
    conn.execute("DELETE FROM sensitive_entries")
    conn.commit()
