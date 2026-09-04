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

Still not built, honestly labeled in the nav: Scheduler, formal
privacy-conscious Logs (spec section 25 — distinct from the security
event log that DOES exist now).
"""

import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.routers import (
    home, personality, memory, contacts, tasks, model_router,
    timing_router, system_router, permissions, approvals, security_router,
    simulation_router, platforms_router, automation_router, workflows_router,
)

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="NightWalker Agent Dashboard")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

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
