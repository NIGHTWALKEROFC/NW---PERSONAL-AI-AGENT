"""
agent/personality/sensitive_store.py

Sensitive information flags — separate from the personality profile,
never merged in. As of Phase 8, the flag content itself is encrypted
at rest (see database/crypto.py for exactly what that protects
against — it's real but limited: it protects the .db file if copied
in isolation, not if someone has both the .db and the key file).

If you have data from before Phase 8, run
scripts/encrypt_existing_data.py once to encrypt it in place.
"""

import datetime

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text


def append_entries(flags: list[str], source_label: str) -> None:
    if not flags:
        return
    conn = get_connection()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conn.executemany(
        "INSERT INTO sensitive_entries (flag, source, added_at) VALUES (?, ?, ?)",
        [(encrypt_text(flag), source_label, now) for flag in flags],
    )
    conn.commit()


def list_entries() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sensitive_entries ORDER BY added_at DESC").fetchall()
    results = []
    for r in rows:
        entry = dict(r)
        entry["flag"] = decrypt_text(entry["flag"])
        results.append(entry)
    return results


def clear_all() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM sensitive_entries")
    conn.commit()
