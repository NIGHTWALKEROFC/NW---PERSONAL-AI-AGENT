"""
dashboard/routers/scheduler_router.py

The dashboard page for Phase 15's scheduler — view registered jobs
and their last run status, plus manual controls (run a job now, or
start/stop the whole scheduler — mainly for testing; the kill switch
on the Security page is the real "stop everything" control).
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.scheduler import scheduler


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/scheduler", response_class=HTMLResponse)
    def scheduler_page(request: Request, message: str | None = None):
        return templates.TemplateResponse(request, "scheduler.html", {
            "jobs": scheduler.list_jobs(),
            "running": scheduler.is_running(),
            "message": message,
        })

    @router.post("/scheduler/jobs/{job_name}/run-now")
    def run_job_now(job_name: str):
        result = scheduler.run_job_now(job_name)
        # scheduler.run_job_now() returns {"error": "..."} ONLY when the job name
        # isn't registered at all; a job that ran (whether it succeeded or itself
        # raised) always returns {"success": bool, "result": ..., "error": ...} —
        # that dict ALSO has an "error" key (None on success), so checking
        # "error" in result alone would wrongly treat every successful run as the
        # not-found case too. "success" not in result is the correct distinguisher.
        if "success" not in result:
            return RedirectResponse(f"/scheduler?message={result['error']}", status_code=303)
        outcome = "succeeded" if result["success"] else "failed"
        return RedirectResponse(f"/scheduler?message=Job+'{job_name}'+{outcome}.", status_code=303)

    @router.post("/scheduler/start")
    def start_scheduler():
        started = scheduler.start()
        message = "Scheduler+started." if started else "Scheduler+was+already+running."
        return RedirectResponse(f"/scheduler?message={message}", status_code=303)

    @router.post("/scheduler/stop")
    def stop_scheduler():
        was_running = scheduler.stop()
        message = "Scheduler+stopped." if was_running else "Scheduler+was+not+running."
        return RedirectResponse(f"/scheduler?message={message}", status_code=303)

    return router
