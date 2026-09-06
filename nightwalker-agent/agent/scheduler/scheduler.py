"""
agent/scheduler/scheduler.py

The recurring-job scheduler flagged as missing since Phase 8's kill
switch docstring ("stop schedulers -> N/A: no scheduler exists yet").

*** WHAT THIS IS ***
A generic, in-process periodic job runner — a lightweight background
thread that calls each registered job's function on its own interval,
forever, until stopped. Nothing scheduler-specific here understands
what a "task" is semantically — see agent/scheduler/jobs.py's
docstring for exactly what it does and doesn't do with task_memory.

*** SAFETY: jobs are responsible for their own safety checks ***
The scheduler itself does not consult the kill switch, master switch,
or permission engine before running a job — exactly like
automation/desktop/workflow_executor.py and agent/actions/
connector_runner.py, safety orchestration lives with whatever is about
to take a real action, not with the thing that triggered it. The jobs
registered by default (agent/scheduler/jobs.py) are pure local
housekeeping (deleting rows that are already meaningless) with no
outward effect on any person or platform, so this distinction doesn't
matter for them — but a future job that DOES take a real action (e.g.
sending a message on a schedule) MUST perform its own permission_engine
/timing_engine checks internally, the same as agent/reply/pipeline.py
already does, rather than assuming the scheduler protects it.

*** THE KILL SWITCH STOPS THIS TOO (Phase 15) ***
agent/security/kill_switch.py's activate() calls stop() here, and
reactivate() calls start() — this is what turns "stop schedulers ->
N/A" into a real, working action.

*** THREADING MODEL ***
One background daemon thread, sleeping in small increments (not one
long sleep per job) so stop() takes effect quickly rather than waiting
out whatever the longest job interval happens to be.

*** RUNNING WITH MULTIPLE PROCESSES ***
If you run both scripts/run_scheduler.py AND the dashboard (which
auto-starts this too — see dashboard/app.py) at the same time, each
process runs its own independent copy of this scheduler, so jobs will
simply run about twice as often as configured. Harmless in practice —
every default job (agent/scheduler/jobs.py) is idempotent, deleting
rows that are already gone is a no-op — but worth knowing rather than
assuming there's cross-process coordination, because there isn't.
"""

import threading
import time
import datetime

from agent.security.security_events import log_event

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_thread: threading.Thread | None = None
_stop_event = threading.Event()

TICK_SECONDS = 5  # how often the loop wakes up to check whether any job is due


def register_job(name: str, func, interval_seconds: int) -> None:
    """
    Registers a job to run every interval_seconds. Calling this again
    with the same name replaces the previous registration, including
    resetting its next-due time to interval_seconds from now.
    """
    with _lock:
        _jobs[name] = {
            "func": func,
            "interval_seconds": interval_seconds,
            "next_due": time.monotonic() + interval_seconds,
            "last_run_at": None,
            "last_result": None,
            "last_error": None,
            "run_count": 0,
        }


def unregister_job(name: str) -> bool:
    with _lock:
        return _jobs.pop(name, None) is not None


def list_jobs() -> list[dict]:
    """A snapshot for the dashboard's Scheduler page — not the live internal state."""
    with _lock:
        return [
            {
                "name": name,
                "interval_seconds": job["interval_seconds"],
                "last_run_at": job["last_run_at"],
                "last_result": job["last_result"],
                "last_error": job["last_error"],
                "run_count": job["run_count"],
            }
            for name, job in _jobs.items()
        ]


def run_job_now(name: str) -> dict:
    """
    Manually triggers a registered job immediately, regardless of
    whether it's currently due — used by the dashboard's per-job
    "Run now" button. Records the result exactly like the normal loop
    does, and resets the job's next-due time from this run.
    """
    with _lock:
        job = _jobs.get(name)
    if job is None:
        return {"error": f"No job registered named '{name}'."}

    return _run_one(name, job)


def _run_one(name: str, job: dict) -> dict:
    try:
        result = job["func"]()
        outcome = {"success": True, "result": result, "error": None}
    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"
        log_event("scheduler_job_failed", f"job={name} error={error_text}")
        outcome = {"success": False, "result": None, "error": error_text}

    with _lock:
        if name in _jobs:  # could have been unregistered mid-run
            _jobs[name]["last_run_at"] = datetime.datetime.utcnow().isoformat() + "Z"
            _jobs[name]["last_result"] = outcome["result"]
            _jobs[name]["last_error"] = outcome["error"]
            _jobs[name]["run_count"] += 1
            _jobs[name]["next_due"] = time.monotonic() + _jobs[name]["interval_seconds"]

    return outcome


def _run_due_jobs() -> None:
    now = time.monotonic()
    with _lock:
        due = [(name, job) for name, job in _jobs.items() if now >= job["next_due"]]

    for name, job in due:
        _run_one(name, job)


def _loop() -> None:
    while not _stop_event.is_set():
        _run_due_jobs()
        _stop_event.wait(TICK_SECONDS)


def start() -> bool:
    """Starts the background thread if it isn't already running. Returns whether it was (newly) started."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop_event.clear()
        _thread = threading.Thread(target=_loop, daemon=True, name="nightwalker-scheduler")
        _thread.start()
    log_event("scheduler_started", f"jobs={list(_jobs.keys())}")
    return True


def stop() -> bool:
    """Signals the background thread to stop and waits briefly for it to exit. Returns whether it was running."""
    global _thread
    was_running = _thread is not None and _thread.is_alive()
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=TICK_SECONDS + 2)
    _thread = None
    if was_running:
        log_event("scheduler_stopped", "")
    return was_running


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()
