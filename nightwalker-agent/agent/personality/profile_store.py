"""
agent/personality/profile_store.py

Loads/saves the personality profile — backed by SQLite
(database/nightwalker.db). As of Phase 8, the profile JSON blob is
encrypted at rest (see database/crypto.py for what that does and does
not protect against). The load_profile()/save_profile()/
profile_exists() interface is unchanged — encryption happens
transparently at the storage boundary, so nothing that calls this
module needed to change.

If you have data from before Phase 8, run
scripts/encrypt_existing_data.py once to encrypt it in place.
"""

import datetime
import json

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text
from agent.personality.profile_schema import empty_profile


def load_profile() -> dict:
    """Load the profile from the database, or return a fresh empty one if none exists yet."""
    conn = get_connection()
    row = conn.execute("SELECT profile_json FROM personality_profile WHERE id = 1").fetchone()
    if row is None:
        return empty_profile()
    decrypted = decrypt_text(row["profile_json"])
    return json.loads(decrypted)


def save_profile(profile: dict) -> None:
    """Save the profile to the database, replacing the previous version, encrypted at rest."""
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    encrypted = encrypt_text(json.dumps(profile, ensure_ascii=False))
    conn.execute(
        "INSERT INTO personality_profile (id, profile_json, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at",
        (encrypted, now),
    )
    conn.commit()


def profile_exists() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT id FROM personality_profile WHERE id = 1").fetchone()
    return row is not None
