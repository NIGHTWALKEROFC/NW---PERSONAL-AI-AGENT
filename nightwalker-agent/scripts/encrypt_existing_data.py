"""
scripts/encrypt_existing_data.py

If you used the agent before Phase 8, your existing data in
database/nightwalker.db is plaintext. This script reads every
sensitive field, encrypts it, and writes it back in place.

Safe to run more than once — decrypt_text() falls back to returning
unchanged text if a value isn't a valid encrypted token, so re-running
this against already-encrypted data just re-encrypts the same
(already-decrypted) plaintext rather than double-encrypting or
crashing.

Usage:
    python scripts/encrypt_existing_data.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text


def migrate_table_column(table: str, id_column: str, content_columns: list[str]) -> int:
    conn = get_connection()
    rows = conn.execute(f"SELECT {id_column}, {', '.join(content_columns)} FROM {table}").fetchall()

    count = 0
    for row in rows:
        row_id = row[id_column]
        updates = {}
        for col in content_columns:
            value = row[col]
            if value is None:
                continue
            # Decrypt first (no-op if already plaintext), then encrypt —
            # this makes the script idempotent whether or not it's the
            # first time it's been run.
            plaintext = decrypt_text(value)
            updates[col] = encrypt_text(plaintext)

        if updates:
            set_clause = ", ".join(f"{col} = ?" for col in updates)
            conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?",
                (*updates.values(), row_id),
            )
            count += 1

    conn.commit()
    return count


def main():
    print("Encrypting existing data in database/nightwalker.db...\n")
    print("(Safe to run more than once — already-encrypted data is left as-is.)\n")

    migrations = [
        ("personality_profile", "id", ["profile_json"]),
        ("sensitive_entries", "id", ["flag"]),
        ("corrections_log", "id", ["original", "edited", "description"]),
        ("conversation_messages", "id", ["content"]),
        ("long_term_memory", "id", ["content"]),
        ("temporary_memory", "id", ["content"]),
        ("contacts", "id", ["relationship_context"]),
        ("contact_memories", "id", ["content"]),
    ]

    for table, id_col, cols in migrations:
        count = migrate_table_column(table, id_col, cols)
        print(f"  {table}: {count} rows encrypted")

    print("\nDone. Your database/secret.key file is what makes this readable again —")
    print("never commit it, never store it alongside a copy of the .db file.")


if __name__ == "__main__":
    main()
