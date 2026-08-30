"""
agent/timing/timing_rules.py

Reads config/timing_config.json and answers: given the current time,
are we in sleep hours, busy hours, or normal active hours?

Uses the laptop's local system time — this assumes the machine's clock
and timezone are set correctly, which is a reasonable assumption for a
personal device but worth stating explicitly rather than silently.

Time ranges support wrapping past midnight (e.g. sleep_hours
23:00-07:00) — a range where start > end is treated as wrapping.
"""

import datetime
import json
import os

TIMING_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "timing_config.json"
)


def load_timing_config() -> dict:
    with open(TIMING_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_time(value: str) -> datetime.time:
    return datetime.datetime.strptime(value, "%H:%M").time()


def _time_in_range(start: datetime.time, end: datetime.time, check: datetime.time) -> bool:
    if start <= end:
        return start <= check <= end
    else:
        # Range wraps past midnight, e.g. 23:00 - 07:00
        return check >= start or check <= end


def get_time_bucket(now: datetime.time | None = None, config: dict | None = None) -> dict:
    """
    Returns {"in_sleep_hours": bool, "in_busy_hours": bool, "busy_label": str|None,
    "in_active_hours": bool} for the given time (defaults to right now, local system time).
    """
    config = config or load_timing_config()
    now = now or datetime.datetime.now().time()

    sleep = config["sleep_hours"]
    active = config["active_hours"]

    in_sleep = _time_in_range(_parse_time(sleep["start"]), _parse_time(sleep["end"]), now)
    in_active = _time_in_range(_parse_time(active["start"]), _parse_time(active["end"]), now)

    in_busy = False
    busy_label = None
    for window in config.get("busy_hours", []):
        if _time_in_range(_parse_time(window["start"]), _parse_time(window["end"]), now):
            in_busy = True
            busy_label = window.get("label")
            break

    return {
        "in_sleep_hours": in_sleep,
        "in_busy_hours": in_busy,
        "busy_label": busy_label,
        "in_active_hours": in_active,
    }
