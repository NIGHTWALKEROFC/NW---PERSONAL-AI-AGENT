"""
database/webhook_inbox_store.py

A tiny durable queue for platforms that deliver messages via webhook
push (Instagram, WhatsApp) rather than a pollable API (Telegram's
getUpdates). webhooks/webhook_server.py enqueues raw incoming messages
here the instant Meta POSTs them; each platform's adapter drains its
own rows via fetch_incoming_messages(). This keeps the exact same
PlatformAdapter interface and the exact same polling-loop runner
pattern (agent/actions/connector_runner.py) working identically for
every connector, regardless of whether the underlying platform pushes
or is polled — the runner script never needs to know which.

`text` and `display_name` are encrypted at rest, consistent with every
other message-content field in this project (see database/crypto.py
and database/memory_store.py) — a webhook payload is real conversation
content the instant it arrives, same as anything already sitting in
conversation_messages.
"""

import datetime

from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def enqueue(
    platform: str,
    platform_user_id: str,
    display_name: str,
    text: str,
    message_id: str,
    timestamp: str,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO webhook_inbox "
        "(platform, platform_user_id, display_name, text, message_id, timestamp, received_at, consumed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (platform, platform_user_id, encrypt_text(display_name), encrypt_text(text), message_id, timestamp, _now()),
    )
    conn.commit()
    return cur.lastrowid


def drain(platform: str) -> list[dict]:
    """
    Returns every unconsumed message for this platform, oldest first,
    and marks them all consumed in the same call — each row is
    returned exactly once across all callers, the same one-shot
    semantics as Telegram's own getUpdates offset.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM webhook_inbox WHERE platform = ? AND consumed = 0 ORDER BY id ASC",
        (platform,),
    ).fetchall()
    if not rows:
        return []

    ids = [row["id"] for row in rows]
    placeholders = ",".join("?" for _ in ids)
    conn.execute(f"UPDATE webhook_inbox SET consumed = 1 WHERE id IN ({placeholders})", ids)
    conn.commit()

    return [
        {
            "id": row["id"],
            "platform": row["platform"],
            "platform_user_id": row["platform_user_id"],
            "display_name": decrypt_text(row["display_name"]),
            "text": decrypt_text(row["text"]),
            "message_id": row["message_id"],
            "timestamp": row["timestamp"],
            "received_at": row["received_at"],
        }
        for row in rows
    ]


def is_message_already_enqueued(platform: str, message_id: str) -> bool:
    """
    Meta's own docs warn webhook deliveries can be retried/duplicated.
    webhooks/webhook_server.py checks this before calling enqueue() so
    a retried delivery can never cause a duplicate reply downstream.
    A blank message_id (shouldn't happen for real Meta payloads, but
    cheap to guard) never counts as a duplicate of another blank one.
    """
    if not message_id:
        return False
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM webhook_inbox WHERE platform = ? AND message_id = ? LIMIT 1",
        (platform, message_id),
    ).fetchone()
    return row is not None
