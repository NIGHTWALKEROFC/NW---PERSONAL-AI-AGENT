"""
dashboard/routers/security_router.py

Spec section 9's security audit screen:
    credentials stored, encrypted databases, external connections,
    permissions, recent security events

Plus the kill switch from spec section 20.

Stated honestly: "credentials stored" is always empty right now
because no platform connectors exist yet to need credentials
(Phase 10). "External connections" is likewise empty for the same
reason.
"""

import os
import json

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from database.crypto import KEY_PATH
from database.db import DB_PATH
from database.state_store import get_state, set_state, delete_state
from agent.security.security_events import get_recent_events
from agent.security.kill_switch import activate, reactivate
from agent.timing.pause_control import is_paused

KILL_SWITCH_STATE_KEY = "kill_switch_previous_levels"


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/security", response_class=HTMLResponse)
    def security_page(request: Request, message: str | None = None):
        events = get_recent_events(limit=15)
        key_exists = os.path.exists(KEY_PATH)
        db_exists = os.path.exists(DB_PATH)
        paused, pause_reason = is_paused()
        kill_switch_active = get_state(KILL_SWITCH_STATE_KEY) is not None

        return templates.TemplateResponse(request, "security.html", {
            "events": events,
            "key_exists": key_exists,
            "db_exists": db_exists,
            "paused": paused,
            "pause_reason": pause_reason,
            "kill_switch_active": kill_switch_active,
            "message": message,
        })

    @router.post("/security/kill-switch/activate")
    def activate_kill_switch():
        result = activate()
        set_state(KILL_SWITCH_STATE_KEY, json.dumps(result["previous_levels"]))
        return RedirectResponse("/security?message=Kill+switch+activated.", status_code=303)

    @router.post("/security/kill-switch/deactivate")
    def deactivate_kill_switch():
        stored = get_state(KILL_SWITCH_STATE_KEY)
        previous_levels = json.loads(stored) if stored else {}
        reactivate(previous_levels)
        delete_state(KILL_SWITCH_STATE_KEY)
        return RedirectResponse("/security?message=Kill+switch+deactivated,+previous+settings+restored.", status_code=303)

    return router
