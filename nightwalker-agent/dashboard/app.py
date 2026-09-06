"""
dashboard/app.py

The local control dashboard, per spec section 18. Binds to
127.0.0.1 (localhost) only by default — see scripts/run_dashboard.py.

Phase 8 additions: Permissions, Approvals (the Approval Center), and
Security (audit screen + kill switch) are now real, working pages —
previously the old Timing page carried a placeholder note about
security; that functionality now lives properly on /security.

Phase 12 fix: automation_router (Phase 11's desktop automation page —
dashboard/routers/automation_router.py, templates/automation.html) was
written back in Phase 11 but never actually registered here, so
/automation and its endpoints have been 404ing since Phase 11 despite
the nav linking to them and the page working code being fully present.
Fixed here, alongside registering the new workflows_router (Phase 12).

Phase 14 addition: DashboardAuthMiddleware (dashboard/auth_middleware.py)
and auth_router (login/logout) — see that middleware's docstring. It's
OPT-IN: with no password ever set via scripts/set_dashboard_password.py,
every route here behaves exactly as it always has, unauthenticated.

Phase 15 addition: the scheduler (agent/scheduler/) auto-starts here on
app startup, registering its default housekeeping jobs — see
scheduler_router.py and agent/scheduler/jobs.py. The kill switch
(Security page) stops it; reactivating restarts it.

Still not built, honestly labeled in the nav: formal privacy-conscious
Logs (spec section 25 — distinct from the security event log that
DOES exist), and the natural-language task planner (spec section 14)
that would give the scheduler's task_memory fields real meaning beyond
the simple expires_at sweep it already does.
"""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.routers import (
    home, personality, memory, contacts, tasks, model_router,
    timing_router, system_router, permissions, approvals, security_router,
    simulation_router, platforms_router, automation_router, workflows_router,
    auth_router, scheduler_router,
)
from dashboard.auth_middleware import DashboardAuthMiddleware
from agent.scheduler import scheduler as _scheduler
from agent.scheduler.jobs import register_default_jobs as _register_default_jobs

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="NightWalker Agent Dashboard")

app.add_middleware(DashboardAuthMiddleware)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app.include_router(auth_router.get_router(templates))
app.include_router(home.get_router(templates))
app.include_router(personality.get_router(templates))
app.include_router(memory.get_router(templates))
app.include_router(contacts.get_router(templates))
app.include_router(tasks.get_router(templates))
app.include_router(model_router.get_router(templates))
app.include_router(timing_router.get_router(templates))
app.include_router(system_router.get_router(templates))
app.include_router(permissions.get_router(templates))
app.include_router(approvals.get_router(templates))
app.include_router(security_router.get_router(templates))
app.include_router(simulation_router.get_router(templates))
app.include_router(platforms_router.get_router(templates))
app.include_router(automation_router.get_router(templates))
app.include_router(workflows_router.get_router(templates))
app.include_router(scheduler_router.get_router(templates))


@app.on_event("startup")
def _start_scheduler_on_launch():
    """Phase 15: the scheduler auto-starts whenever the dashboard does, so
    housekeeping runs without needing a separate scripts/run_scheduler.py process."""
    _register_default_jobs()
    _scheduler.start()


@app.on_event("shutdown")
def _stop_scheduler_on_shutdown():
    """Matches the startup hook above — a clean dashboard shutdown should leave
    no background thread it started still running, and the audit trail should
    show a clean stop rather than the thread just dying with the process."""
    _scheduler.stop()
