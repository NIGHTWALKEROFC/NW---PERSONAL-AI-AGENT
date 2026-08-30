"""
agent/timing/pause_control.py

Manual pause, per spec section 5/20:
    pause 10 minutes
    pause 1 hour
    pause until manually resumed

Stored in the agent_state table so it survives closing and reopening
the terminal — a pause you set shouldn't silently disappear just
because the process restarted.

This is NOT the full security kill switch from spec section 20 — that
also needs to stop schedulers, revoke sessions, and disable outgoing
actions, none of which exist yet (no scheduler, no platform
connectors). This is specifically the timing engine's pause, which the
kill switch in a later phase can build on top of.
"""

import datetime

from database.state_store import get_state, set_state, delete_state

PAUSE_STATE_KEY = "manual_pause_until"
PAUSE_INDEFINITE_VALUE = "indefinite"


def pause_for(minutes: int) -> str:
    """Pauses for a fixed duration. Returns the ISO timestamp it will resume at."""
    resume_at = (datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)).isoformat() + "Z"
    set_state(PAUSE_STATE_KEY, resume_at)
    return resume_at


def pause_indefinitely() -> None:
    """Pauses until explicitly resumed — no automatic expiry."""
    set_state(PAUSE_STATE_KEY, PAUSE_INDEFINITE_VALUE)


def resume() -> None:
    """Clears any active pause, immediately."""
    delete_state(PAUSE_STATE_KEY)


def is_paused() -> tuple[bool, str | None]:
    """
    Returns (paused: bool, reason: str | None).
    An expired timed pause is treated as not-paused and is cleaned up
    automatically the next time this is checked.
    """
    value = get_state(PAUSE_STATE_KEY)
    if value is None:
        return False, None

    if value == PAUSE_INDEFINITE_VALUE:
        return True, "Manually paused indefinitely."

    try:
        resume_at = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        # Corrupted state value — fail safe by clearing it rather than
        # trusting an unparseable pause forever.
        delete_state(PAUSE_STATE_KEY)
        return False, None

    now = datetime.datetime.now(datetime.timezone.utc)
    if now < resume_at:
        return True, f"Manually paused until {value}."
    else:
        delete_state(PAUSE_STATE_KEY)
        return False, None
