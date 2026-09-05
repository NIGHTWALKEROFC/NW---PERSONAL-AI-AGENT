"""
dashboard/routers/auth_router.py

Login and logout for Phase 14's dashboard authentication. See
dashboard/auth_middleware.py for how every other route gets protected,
and agent/security/dashboard_auth.py for the underlying password/
session logic.

device_label is captured automatically from the browser's User-Agent
header at login time (not asked for) — good enough to tell devices
apart on the Security page ("which of these sessions is my phone")
without adding friction to logging in.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.security.dashboard_auth import (
    has_password_set, verify_password, create_session, revoke_session,
    record_login_attempt, is_locked_out,
)
from dashboard.auth_middleware import SESSION_COOKIE_NAME
from agent.security.security_events import log_event


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/", error: str | None = None):
        if not has_password_set():
            # Nothing to log into — send them straight to the dashboard, matching
            # the middleware's own "no password set = open access" behavior.
            return RedirectResponse("/", status_code=303)

        return templates.TemplateResponse(request, "login.html", {"next": next, "error": error})

    @router.post("/login")
    def login_submit(request: Request, password: str = Form(...), next: str = Form("/")):
        source_ip = request.client.host if request.client else "unknown"

        if is_locked_out(source_ip):
            log_event("dashboard_login_locked_out", f"source_ip={source_ip}")
            return RedirectResponse(
                f"/login?error=Too+many+failed+attempts.+Wait+15+minutes+and+try+again.&next={next}",
                status_code=303,
            )

        success = verify_password(password)
        record_login_attempt(source_ip, success)

        if not success:
            log_event("dashboard_login_failed", f"source_ip={source_ip}")
            return RedirectResponse(f"/login?error=Incorrect+password.&next={next}", status_code=303)

        device_label = request.headers.get("user-agent", "")[:200]
        session_id = create_session(device_label=device_label)
        log_event("dashboard_login_succeeded", f"source_ip={source_ip} device={device_label}")

        response = RedirectResponse(next or "/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=(request.url.scheme == "https"),
            max_age=60 * 60 * 24 * 30,  # 30 days — matches dashboard_auth's default session TTL
        )
        return response

    @router.post("/logout")
    def logout(request: Request):
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if session_id:
            revoke_session(session_id)
            log_event("dashboard_logout", "")

        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    return router
