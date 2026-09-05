"""
agent/security/kill_switch.py

Spec section 20's "STOP EVERYTHING" kill switch, scoped honestly:

    stop agent actions        -> real: triggers indefinite pause (Phase 6)
    stop automation           -> N/A: no automation system exists yet (Phase 11)
    stop schedulers           -> N/A: no scheduler exists yet
    revoke dashboard sessions -> real (Phase 14): every logged-in device is
                                 logged out immediately. This is DASHBOARD
                                 login sessions only (agent/security/
                                 dashboard_auth.py) — it does not touch
                                 platform connector credentials (Telegram/
                                 Instagram/WhatsApp tokens), which are a
                                 separate, still-nonexistent "session" concept.
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
from agent.security.dashboard_auth import revoke_all_sessions, has_password_set

_ACTIONS_TO_DISABLE = ["send_normal_reply", "story_related_action"]


def activate() -> dict:
    """Triggers everything that can actually be stopped right now. Returns a summary."""
    pause_indefinitely()

    previous_levels = {}
    for action in _ACTIONS_TO_DISABLE:
        previous_levels[action] = get_permission(action)
        set_permission(action, "DISABLED")

    sessions_revoked = revoke_all_sessions() if has_password_set() else 0

    log_event("kill_switch_activated", f"disabled: {_ACTIONS_TO_DISABLE}, sessions_revoked: {sessions_revoked}")

    return {
        "paused": True,
        "disabled_actions": _ACTIONS_TO_DISABLE,
        "previous_levels": previous_levels,
        "sessions_revoked": sessions_revoked,
        "not_applicable": [
            "stop automation (none exists yet)",
            "stop schedulers (none exists yet)",
        ],
    }


def reactivate(previous_levels: dict) -> None:
    """Reverses activate() — resumes timing and restores the previous permission levels."""
    resume_timing()
    for action, level in previous_levels.items():
        set_permission(action, level)
    log_event("kill_switch_deactivated", f"restored: {previous_levels}")
