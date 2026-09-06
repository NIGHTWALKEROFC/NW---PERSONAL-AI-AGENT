"""
agent/security/kill_switch.py

Spec section 20's "STOP EVERYTHING" kill switch, scoped honestly:

    stop agent actions        -> real: triggers indefinite pause (Phase 6)
    stop automation           -> N/A: no automation system exists yet (Phase 11)
    stop schedulers           -> real (Phase 15): agent/scheduler/scheduler.py's
                                 background thread is stopped immediately.
                                 reactivate() restarts it.
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
than that would be misleading. As of Phase 15, "automation" (Phase 11's
desktop automation / Phase 12's workflows) remains the one N/A: those
already require a human to explicitly initiate and dry-run-preview
every action, so there's no standing background process for a kill
switch to interrupt the way there is for the scheduler.
"""

from agent.timing.pause_control import pause_indefinitely, resume as resume_timing
from agent.security.permission_engine import set_permission, get_permission
from agent.security.security_events import log_event
from agent.security.dashboard_auth import revoke_all_sessions, has_password_set
from agent.scheduler import scheduler

_ACTIONS_TO_DISABLE = ["send_normal_reply", "story_related_action"]


def activate() -> dict:
    """Triggers everything that can actually be stopped right now. Returns a summary."""
    pause_indefinitely()

    previous_levels = {}
    for action in _ACTIONS_TO_DISABLE:
        previous_levels[action] = get_permission(action)
        set_permission(action, "DISABLED")

    sessions_revoked = revoke_all_sessions() if has_password_set() else 0
    scheduler_was_running = scheduler.stop()

    log_event(
        "kill_switch_activated",
        f"disabled: {_ACTIONS_TO_DISABLE}, sessions_revoked: {sessions_revoked}, "
        f"scheduler_was_running: {scheduler_was_running}",
    )

    return {
        "paused": True,
        "disabled_actions": _ACTIONS_TO_DISABLE,
        "previous_levels": previous_levels,
        "sessions_revoked": sessions_revoked,
        "scheduler_stopped": scheduler_was_running,
        "not_applicable": [
            "stop automation (none exists as a standing process — every automation action already requires explicit human initiation and dry-run preview)",
        ],
    }


def reactivate(previous_levels: dict) -> None:
    """Reverses activate() — resumes timing, restores previous permission levels, and restarts the scheduler."""
    resume_timing()
    for action, level in previous_levels.items():
        set_permission(action, level)
    scheduler.start()
    log_event("kill_switch_deactivated", f"restored: {previous_levels}")
