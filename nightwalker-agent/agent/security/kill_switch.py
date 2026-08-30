"""
agent/security/kill_switch.py

Spec section 20's "STOP EVERYTHING" kill switch, scoped honestly:

    stop agent actions        -> real: triggers indefinite pause (Phase 6)
    stop automation           -> N/A: no automation system exists yet (Phase 11)
    stop schedulers           -> N/A: no scheduler exists yet (Phase 14)
    revoke temporary sessions -> N/A: no sessions exist yet (Phase 10 — platform connectors)
    disable outgoing actions  -> real: sets send_normal_reply and story_related_action
                                 to DISABLED (reversible — see reactivate())
    preserve security logs    -> real: this action itself is logged, and nothing here
                                 deletes any log or memory

This is not a complete kill switch yet — it's exactly as complete as
the systems it would need to reach into currently are. Calling it more
than that would be misleading.
"""

from agent.timing.pause_control import pause_indefinitely, resume as resume_timing
from agent.security.permission_engine import set_permission, get_permission
from agent.security.security_events import log_event

_ACTIONS_TO_DISABLE = ["send_normal_reply", "story_related_action"]


def activate() -> dict:
    """Triggers everything that can actually be stopped right now. Returns a summary."""
    pause_indefinitely()

    previous_levels = {}
    for action in _ACTIONS_TO_DISABLE:
        previous_levels[action] = get_permission(action)
        set_permission(action, "DISABLED")

    log_event("kill_switch_activated", f"disabled: {_ACTIONS_TO_DISABLE}")

    return {
        "paused": True,
        "disabled_actions": _ACTIONS_TO_DISABLE,
        "previous_levels": previous_levels,
        "not_applicable": [
            "stop automation (none exists yet)",
            "stop schedulers (none exists yet)",
            "revoke sessions (no platform connectors exist yet)",
        ],
    }


def reactivate(previous_levels: dict) -> None:
    """Reverses activate() — resumes timing and restores the previous permission levels."""
    resume_timing()
    for action, level in previous_levels.items():
        set_permission(action, level)
    log_event("kill_switch_deactivated", f"restored: {previous_levels}")
