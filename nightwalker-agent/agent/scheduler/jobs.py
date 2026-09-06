"""
agent/scheduler/jobs.py

The built-in housekeeping jobs registered by default (see
register_default_jobs(), called from scripts/run_scheduler.py and
dashboard/app.py's startup). Every job here is pure local database
hygiene — deleting rows that are already meaningless (expired
sessions, old login attempts, consumed webhook queue entries, overdue
tasks) — nothing here sends a message, contacts a platform, or takes
any action a person would notice. That's why none of them need to
consult the kill switch, permission engine, or timing engine — see
scheduler.py's "SAFETY" section for why that's a real distinction, not
an oversight.

*** WHAT THIS DELIBERATELY DOES NOT DO ***
This does NOT implement the natural-language task planner from spec
section 14 — turning a task_memory row's free-text `schedule` or
`trigger_condition` (e.g. "watch this conversation and let me know if
I need to respond") into an actual periodic check-and-act job. That
planner doesn't exist, and those two columns' formats were never
specified, so there's no well-defined behavior to run here — building
one would mean inventing an interpretation of a natural-language field
that could easily be wrong. The one column this DOES act on is
`expires_at`, which is unambiguous (an ISO timestamp) and has existed
since Phase 4 with nothing ever checking it — expire_overdue_tasks_job
below closes exactly that gap and no more.
"""

import datetime

from agent.scheduler.scheduler import register_job
from agent.security.dashboard_auth import prune_expired_sessions, prune_old_login_attempts
from database.webhook_inbox_store import prune_consumed
from database.task_store import list_tasks, update_task_status

HOUR = 3600


def prune_dashboard_sessions_job() -> str:
    count = prune_expired_sessions()
    return f"removed {count} expired/revoked session row(s)"


def prune_login_attempts_job() -> str:
    count = prune_old_login_attempts(older_than_days=30)
    return f"removed {count} login attempt row(s) older than 30 days"


def prune_webhook_inbox_job() -> str:
    count = prune_consumed(older_than_days=7)
    return f"removed {count} consumed webhook inbox row(s) older than 7 days"


def expire_overdue_tasks_job() -> str:
    """The only piece of task_memory's scheduling fields this scheduler acts
    on — see module docstring for why `schedule`/`trigger_condition` are left alone."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    expired_count = 0
    for task in list_tasks():
        if task["status"] in ("pending", "active") and task["expires_at"] and task["expires_at"] < now:
            update_task_status(task["id"], "expired")
            expired_count += 1
    return f"expired {expired_count} overdue task(s)"


def register_default_jobs() -> None:
    register_job("prune_dashboard_sessions", prune_dashboard_sessions_job, interval_seconds=6 * HOUR)
    register_job("prune_login_attempts", prune_login_attempts_job, interval_seconds=24 * HOUR)
    register_job("prune_webhook_inbox", prune_webhook_inbox_job, interval_seconds=24 * HOUR)
    register_job("expire_overdue_tasks", expire_overdue_tasks_job, interval_seconds=HOUR)
