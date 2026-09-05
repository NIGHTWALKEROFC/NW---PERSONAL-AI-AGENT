"""
dashboard/auth_middleware.py

Enforces login for the whole dashboard app, once (and only once) a
password has been set — see agent/security/dashboard_auth.py's
"OPT-IN, NOT FORCED" section for why this checks has_password_set()
on every request rather than assuming a fixed on/off state.

Applied as Starlette middleware (dashboard/app.py) rather than a
per-route dependency, specifically so adding auth required touching
NO existing router file — every router from every previous phase works
completely unchanged; this middleware sits in front of all of them.

Allowed through without a session, always:
    /login   (GET renders the form, POST checks the password)
    /static  (CSS — nothing sensitive)
Everything else requires a valid, non-revoked, non-expired session —
enforced by checking the "nw_session" cookie against
agent/security/dashboard_auth.validate_session() on every request.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from agent.security.dashboard_auth import has_password_set, validate_session

SESSION_COOKIE_NAME = "nw_session"

_PUBLIC_PATH_PREFIXES = ("/login", "/static")


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not has_password_set():
            # Opt-in: no password has ever been set, so behave exactly like every
            # phase before this one — open access, protected only by not being
            # reachable from outside this machine.
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in _PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not validate_session(session_id):
            return RedirectResponse(f"/login?next={request.url.path}", status_code=303)

        return await call_next(request)
