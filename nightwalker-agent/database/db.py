"""
database/db.py

Single SQLite database for the entire memory architecture. As of
Phase 8, sensitive content fields in this database are encrypted at
the application level before being written — see database/crypto.py
for exactly what that does and doesn't protect against. The schema
itself is unchanged by that (still plain TEXT columns); encryption
happens in the store modules, not here.

Phase 8 additions to the schema: pending_approvals (the approval
queue) and security_events (a simple audit log).
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "nightwalker.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS personality_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensitive_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flag TEXT NOT NULL,
    source TEXT,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corrections_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    original TEXT NOT NULL,
    edited TEXT NOT NULL,
    tags TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    platform TEXT,
    relationship_context TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    memory_layer TEXT NOT NULL DEFAULT 'short_term',
    created_at TEXT NOT NULL,
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS long_term_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    source TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS temporary_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    trigger_condition TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    schedule TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    contact_id INTEGER,
    payload TEXT NOT NULL,
    reasoning TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_contact ON conversation_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_layer ON conversation_messages(memory_layer);
CREATE INDEX IF NOT EXISTS idx_contact_memories_contact ON contact_memories(contact_id);
CREATE INDEX IF NOT EXISTS idx_temporary_memory_expires ON temporary_memory(expires_at);
CREATE INDEX IF NOT EXISTS idx_task_memory_status ON task_memory(status);
CREATE INDEX IF NOT EXISTS idx_pending_approvals_status ON pending_approvals(status);
"""


def get_connection() -> sqlite3.Connection:
    """
    Returns a connection with schema guaranteed to exist. Safe to call
    repeatedly — CREATE TABLE IF NOT EXISTS is cheap and idempotent.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn
