"""
dashboard/routers/timing_router.py

Covers part of the SECURITY dashboard section from spec section 18 —
specifically the manual pause / "STOP EVERYTHING"-adjacent control
that DOES exist (Phase 6), plus a view of the timing configuration.

This is NOT the full security kill switch from spec section 20 (that
also needs to stop schedulers and revoke sessions, neither of which
exist yet) — it's honestly scoped to what Phase 6 actually built.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.timing.pause_control import is_paused, pause_for, pause_indefinitely, resume
from agent.timing.timing_rules import load_timing_config, get_time_bucket


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/timing", response_class=HTMLResponse)
    def timing_page(request: Request, message: str | None = None):
        paused, reason = is_paused()
        config = load_timing_config()
        bucket = get_time_bucket(config=config)

        return templates.TemplateResponse(request, "timing.html", {
            "paused": paused,
            "reason": reason,
            "config": config,
            "bucket": bucket,
            "message": message,
        })

    @router.post("/timing/pause")
    def pause(duration: str = Form(...)):
        if duration == "10min":
            pause_for(10)
            msg = "Paused+for+10+minutes."
        elif duration == "1hour":
            pause_for(60)
            msg = "Paused+for+1+hour."
        elif duration == "indefinite":
            pause_indefinitely()
            msg = "Paused+indefinitely."
        else:
            msg = "No+change."
        return RedirectResponse(f"/timing?message={msg}", status_code=303)

    @router.post("/timing/resume")
    def resume_now():
        resume()
        return RedirectResponse("/timing?message=Resumed.", status_code=303)

    return router
