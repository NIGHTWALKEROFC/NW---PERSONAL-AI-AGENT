"""
database/db.py

Single SQLite database for the entire memory architecture:
short-term, long-term, contact, task, and temporary memory, plus the
personality profile, sensitive-information flags, and the corrections
log (all previously separate JSON files in Phase 2-3 — now one file,
one place to eventually encrypt in Phase 8).

Every consumer should go through get_connection() rather than opening
the file directly, so schema initialization is guaranteed to have run.
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

CREATE INDEX IF NOT EXISTS idx_conversation_messages_contact ON conversation_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_layer ON conversation_messages(memory_layer);
CREATE INDEX IF NOT EXISTS idx_contact_memories_contact ON contact_memories(contact_id);
CREATE INDEX IF NOT EXISTS idx_temporary_memory_expires ON temporary_memory(expires_at);
CREATE INDEX IF NOT EXISTS idx_task_memory_status ON task_memory(status);
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
