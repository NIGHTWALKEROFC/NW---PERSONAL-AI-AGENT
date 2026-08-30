"""
agent/timing/timing_engine.py

Ties together everything the spec's response-timing engine needs to
decide:
- Is the agent manually paused right now? (hard stop)
- Is it currently sleep hours? (hard stop — don't act while the real
  person would be asleep)
- Is it busy hours? (still allowed, but with an increased delay)
- What delay should apply, based on YOUR real historical reply speed
  to this contact where that data exists, falling back to a configured
  default where it doesn't?

This module only calculates and returns a decision — it does not sleep
the process, schedule anything, or send any message. Wiring this into
an actual send loop is Phase 10 (platform connectors), which doesn't
exist yet. Never used to evade platform detection — the intent is
purely to avoid the agent behaving in an obviously robotic,
instant-reply way, matching the spec's stated goal directly.
"""

from agent.timing.pause_control import is_paused
from agent.timing.timing_rules import get_time_bucket, load_timing_config
from agent.timing.history_analyzer import get_average_reply_delay
from database.contact_store import get_contact_by_name


def decide_timing(contact_name: str | None = None) -> dict:
    """
    Returns:
    {
        "allowed": bool,
        "delay_seconds": float | None,
        "reason": str,
        "based_on": "manual_pause" | "sleep_hours" | "history" | "cold_start_default",
        "sample_count": int | None,
    }

    allowed=False means don't act at all right now (paused or asleep).
    allowed=True with a delay_seconds means: wait this long, then it's fine to reply.
    """
    paused, pause_reason = is_paused()
    if paused:
        return {
            "allowed": False,
            "delay_seconds": None,
            "reason": pause_reason,
            "based_on": "manual_pause",
            "sample_count": None,
        }

    config = load_timing_config()
    bucket = get_time_bucket(config=config)

    if bucket["in_sleep_hours"]:
        return {
            "allowed": False,
            "delay_seconds": None,
            "reason": "Currently within configured sleep hours — not a good time to act.",
            "based_on": "sleep_hours",
            "sample_count": None,
        }

    contact = get_contact_by_name(contact_name) if contact_name else None
    contact_id = contact["id"] if contact else None

    history_result = None
    if contact_id is not None:
        history_result = get_average_reply_delay(
            contact_id,
            min_samples=config["min_history_samples_for_contact"],
            min_delay=config["min_delay_seconds"],
            max_delay=config["max_delay_seconds"],
        )

    if history_result is not None:
        delay = history_result["delay_seconds"]
        based_on = "history"
        sample_count = history_result["sample_count"]
        reason = f"Based on {sample_count} real historical replies to this contact (median delay)."
    else:
        delay = config["cold_start_default_delay_seconds"]
        based_on = "cold_start_default"
        sample_count = None
        reason = "No sufficient real history for this contact yet — using the configured default delay."

    if bucket["in_busy_hours"]:
        delay *= config["busy_hours_delay_multiplier"]
        reason += f" Extended because it's currently a busy period ({bucket['busy_label']})."
    elif not bucket["in_active_hours"]:
        delay *= 1.5
        reason += " Slightly extended — currently outside typical active hours."

    delay = max(config["min_delay_seconds"], min(config["max_delay_seconds"], delay))

    return {
        "allowed": True,
        "delay_seconds": round(delay, 1),
        "reason": reason,
        "based_on": based_on,
        "sample_count": sample_count,
    }
