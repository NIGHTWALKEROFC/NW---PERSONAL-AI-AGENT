"""
database/wipe.py

Implements spec section 31: "DELETE ALL PERSONAL DATA — which securely
removes local personality, memories, imported conversations and
generated personal profiles."

Scope, deliberately: this wipes the personality profile, sensitive
flags, corrections log, all conversation history (both short-term and
imported), long-term/temporary memory, all contacts + their memories,
and (Phase 8) the approval queue — since approval payloads contain
draft conversation text, the same category of data as the rest.

It does NOT wipe task_memory, agent_state (pause status), or
security_events — those are operational/audit records, not personal
conversation or personality data.

This is destructive and irreversible by design — there is no undo.
The dashboard requires a typed confirmation before calling this; this
function itself does not ask for confirmation, so any caller must
implement that check first.
"""

from database.db import get_connection


def wipe_all_personal_data() -> dict:
    """Deletes everything in scope. Returns a count of rows removed per table."""
    conn = get_connection()
    counts = {}

    tables = [
        "personality_profile",
        "sensitive_entries",
        "corrections_log",
        "conversation_messages",
        "long_term_memory",
        "temporary_memory",
        "contact_memories",
        "contacts",
        "pending_approvals",
    ]

    for table in tables:
        cur = conn.execute(f"DELETE FROM {table}")
        counts[table] = cur.rowcount

    conn.commit()
    return counts
