"""
automation/desktop/master_switch.py

A hard, separate on/off switch for ALL real (non-dry-run) desktop
automation, defaulting to OFF. This exists as defense in depth beyond
the per-action permission engine — given that I cannot personally
verify any of the actual click/type/screenshot code against a real
display, an extra, deliberately-flipped-on-purpose switch is a
reasonable additional safeguard before anything in this package can
actually move a mouse or press a key for real.

Persisted via the same agent_state table used for the timing pause and
kill switch (database/state_store.py) — survives a restart.
"""

from database.state_store import get_state, set_state

MASTER_SWITCH_KEY = "desktop_automation_master_enabled"


def is_enabled() -> bool:
    return get_state(MASTER_SWITCH_KEY) == "true"


def enable() -> None:
    set_state(MASTER_SWITCH_KEY, "true")


def disable() -> None:
    set_state(MASTER_SWITCH_KEY, "false")
