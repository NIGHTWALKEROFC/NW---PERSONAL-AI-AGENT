"""
scripts/migrate_json_to_sqlite.py

If you ran the onboarding interview, imported conversations, or logged
corrections BEFORE Phase 4, that data is sitting in old JSON files:

    database/personality_profile.json
    database/sensitive_profile.json
    database/corrections_log.json

Phase 4 moved all storage into database/nightwalker.db (SQLite). This
script is a one-time bridge: it reads whichever of those JSON files
still exist and inserts their contents into the new database.

Non-destructive by design: old JSON files are renamed to *.migrated
rather than deleted, in case anything needs double-checking. Safe to
run even if some or all of the JSON files don't exist — it just skips
what's missing.

Usage:
    python scripts/migrate_json_to_sqlite.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import get_connection

DATABASE_DIR = os.path.join(os.path.dirname(__file__), "..", "database")

PROFILE_JSON = os.path.join(DATABASE_DIR, "personality_profile.json")
SENSITIVE_JSON = os.path.join(DATABASE_DIR, "sensitive_profile.json")
CORRECTIONS_JSON = os.path.join(DATABASE_DIR, "corrections_log.json")


def _rename_migrated(path: str) -> None:
    if os.path.exists(path):
        os.rename(path, path + ".migrated")


def migrate_profile() -> bool:
    if not os.path.exists(PROFILE_JSON):
        return False
    with open(PROFILE_JSON, "r", encoding="utf-8") as f:
        profile = json.load(f)

    import datetime
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conn.execute(
        "INSERT INTO personality_profile (id, profile_json, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET profile_json = excluded.profile_json, updated_at = excluded.updated_at",
        (json.dumps(profile, ensure_ascii=False), now),
    )
    conn.commit()
    _rename_migrated(PROFILE_JSON)
    return True


def migrate_sensitive() -> int:
    if not os.path.exists(SENSITIVE_JSON):
        return 0
    with open(SENSITIVE_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    conn = get_connection()
    conn.executemany(
        "INSERT INTO sensitive_entries (flag, source, added_at) VALUES (?, ?, ?)",
        [(e.get("flag", ""), e.get("source", ""), e.get("added_at", "")) for e in entries],
    )
    conn.commit()
    _rename_migrated(SENSITIVE_JSON)
    return len(entries)


def migrate_corrections() -> int:
    if not os.path.exists(CORRECTIONS_JSON):
        return 0
    with open(CORRECTIONS_JSON, "r", encoding="utf-8") as f:
        entries = json.load(f)

    conn = get_connection()
    conn.executemany(
        "INSERT INTO corrections_log (timestamp, original, edited, tags, description) VALUES (?, ?, ?, ?, ?)",
        [
            (
                e.get("timestamp", ""),
                e.get("original", ""),
                e.get("edited", ""),
                json.dumps(e.get("tags", [])),
                e.get("description", ""),
            )
            for e in entries
        ],
    )
    conn.commit()
    _rename_migrated(CORRECTIONS_JSON)
    return len(entries)


def main():
    print("Migrating Phase 2/3 JSON data into database/nightwalker.db...\n")

    if migrate_profile():
        print("  Personality profile migrated. (personality_profile.json -> personality_profile.json.migrated)")
    else:
        print("  No personality_profile.json found — nothing to migrate.")

    sensitive_count = migrate_sensitive()
    if sensitive_count:
        print(f"  {sensitive_count} sensitive entries migrated. (sensitive_profile.json -> sensitive_profile.json.migrated)")
    else:
        print("  No sensitive_profile.json found — nothing to migrate.")

    corrections_count = migrate_corrections()
    if corrections_count:
        print(f"  {corrections_count} correction log entries migrated. (corrections_log.json -> corrections_log.json.migrated)")
    else:
        print("  No corrections_log.json found — nothing to migrate.")

    print("\nDone. The .migrated files are kept as a backup — safe to delete manually once you've verified everything looks right.")


if __name__ == "__main__":
    main()
