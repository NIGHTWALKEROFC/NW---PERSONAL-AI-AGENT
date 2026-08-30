"""
agent/timing/history_analyzer.py

Computes how long you actually took to reply to a given contact, based
on real timestamped message history — not guesses. This only has data
once conversation_importer.py has persisted imported history (Phase 6
addition) or once real platform connectors (Phase 10, not built yet)
start logging real incoming/outgoing messages with timestamps.

Honest limitation: until one of those sources exists for a given
contact, there is no real history to analyze, and
get_average_reply_delay() correctly returns None — the caller
(timing_engine.py) falls back to a configured cold-start default
rather than this module inventing a plausible-sounding number with no
evidence behind it.
"""

import datetime
import statistics

from database.memory_store import get_messages_for_contact


def get_contact_reply_gaps(contact_id: int) -> list[float]:
    """
    Returns a list of gap durations in seconds — each one the time between
    a message FROM the contact (any role that isn't 'me' or 'agent') and
    the next message where role == 'me' that followed it.
    """
    messages = get_messages_for_contact(contact_id)
    gaps = []

    pending_incoming_time = None
    for msg in messages:
        try:
            ts = datetime.datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if msg["role"] not in ("me", "agent"):
            # This is the contact speaking — start waiting for a reply.
            pending_incoming_time = ts
        elif msg["role"] == "me" and pending_incoming_time is not None:
            gap_seconds = (ts - pending_incoming_time).total_seconds()
            if gap_seconds >= 0:  # ignore out-of-order or malformed timestamps
                gaps.append(gap_seconds)
            pending_incoming_time = None  # reset — waiting for the next incoming message

    return gaps


def get_average_reply_delay(contact_id: int, min_samples: int, min_delay: float, max_delay: float) -> dict | None:
    """
    Returns {"delay_seconds": float, "sample_count": int} using the median
    of real historical gaps (median resists outliers like "went to sleep
    and replied 8 hours later" skewing the number badly), clipped to the
    configured min/max bounds.

    Returns None if there isn't enough real history yet (cold start) —
    the caller should use a config default instead, not treat None as zero.
    """
    gaps = get_contact_reply_gaps(contact_id)
    if len(gaps) < min_samples:
        return None

    median_delay = statistics.median(gaps)
    clipped = max(min_delay, min(max_delay, median_delay))

    return {"delay_seconds": clipped, "sample_count": len(gaps)}
