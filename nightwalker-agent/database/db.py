"""
database/db.py

Single SQLite database for the entire memory architecture. Sensitive
content fields are encrypted at the application level — see
database/crypto.py.

Phase 10 addition: contacts gets a new `platform_id` column — the
platform-specific identifier (e.g. a Telegram chat ID) needed to
actually send a message to that contact. Existing databases get this
column added automatically via ALTER TABLE, since CREATE TABLE IF NOT
EXISTS alone doesn't add columns to a table that already exists.
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

# Columns added after a table already existed in an earlier phase —
# CREATE TABLE IF NOT EXISTS doesn't retroactively add these, so they're
# applied explicitly and idempotently (checked against pragma table_info first).
_COLUMN_MIGRATIONS = [
    ("contacts", "platform_id", "TEXT"),
]


def _apply_column_migrations(conn: sqlite3.Connection) -> None:
    for table, column, col_type in _COLUMN_MIGRATIONS:
        existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def get_connection() -> sqlite3.Connection:
    """
    Returns a connection with schema guaranteed to exist and up to date.
    Safe to call repeatedly.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _apply_column_migrations(conn)
    conn.commit()
    return conn
