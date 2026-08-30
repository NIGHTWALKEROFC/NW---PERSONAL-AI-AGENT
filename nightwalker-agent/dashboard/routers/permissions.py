"""
dashboard/routers/permissions.py

The PERMISSIONS dashboard section from spec section 18, wired to
agent/security/permission_engine.py.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.security.permission_engine import load_permissions, set_permission, VALID_LEVELS
from agent.security.security_events import log_event


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/permissions", response_class=HTMLResponse)
    def permissions_page(request: Request, message: str | None = None):
        permissions = load_permissions()
        return templates.TemplateResponse(request, "permissions.html", {
            "permissions": permissions,
            "valid_levels": sorted(VALID_LEVELS),
            "message": message,
        })

    @router.post("/permissions/update")
    def update_permission(action_type: str = Form(...), level: str = Form(...)):
        set_permission(action_type, level)
        log_event("permission_changed", f"action_type={action_type}, new_level={level} (via dashboard)")
        return RedirectResponse(f"/permissions?message=Updated+{action_type}+to+{level}.", status_code=303)

    return router
