"""
agent/personality/profile_store.py

Loads/saves the personality profile — now backed by SQLite
(database/nightwalker.db) instead of a standalone JSON file.

This is the swap promised back in Phase 2: the interface
(load_profile() / save_profile() / profile_exists()) is unchanged, so
nothing in profile_extractor.py, onboarding.py, conversation_importer.py,
or correction_learning.py needed to change. The profile itself is still
a plain nested dict — it's just stored as one JSON blob in a single-row
table rather than a loose file, which puts it in the same database file
as everything else ahead of Phase 8 encryption (one file to protect
instead of several scattered ones).

If you have an existing database/personality_profile.json from before
this phase, run scripts/migrate_json_to_sqlite.py once to bring it into
the database — it is not read automatically.
"""

import datetime
import json

from database.db import get_connection
from agent.personality.profile_schema import empty_profile


def load_profile() -> dict:
    """Load the profile from the database, or return a fresh empty one if none exists yet."""
    conn = get_connection()
    row = conn.execute("SELECT profile_json FROM personality_profile WHERE id = 1").fetchone()
    if row is None:
        return empty_profile()
    return json.loads(row["profile_json"])


def save_profile(profile: dict) -> None:
    """Save the profile to the database, replacing the previous version."""
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conn.execute(
        "INSERT INTO personality_profile (id, profile_json, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at",
        (json.dumps(profile, ensure_ascii=False), now),
    )
    conn.commit()


def profile_exists() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT id FROM personality_profile WHERE id = 1").fetchone()
    return row is not None
