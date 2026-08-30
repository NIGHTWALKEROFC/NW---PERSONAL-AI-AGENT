"""
dashboard/routers/home.py

The HOME dashboard section from spec section 18:
    agent status, model, cpu/ram usage, active tasks, pending
    approvals, recent activity, security alerts

"pending approvals" and "security alerts" are honestly shown as
not-yet-available — there is no permission engine (Phase 8) generating
approval requests yet, and no security event log (also Phase 8).
"""

import psutil
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
from database.task_store import list_tasks
from agent.timing.pause_control import is_paused


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def home(request: Request):
        model_name = get_active_model()
        client = ModelClient(model_name)
        ollama_up = client.is_available()

        paused, pause_reason = is_paused()

        active_tasks = [t for t in list_tasks() if t["status"] in ("pending", "active")]

        cpu_percent = psutil.cpu_percent(interval=0.3)
        ram = psutil.virtual_memory()

        return templates.TemplateResponse(request, "home.html", {
            "model_name": model_name,
            "ollama_up": ollama_up,
            "paused": paused,
            "pause_reason": pause_reason,
            "active_tasks_count": len(active_tasks),
            "cpu_percent": cpu_percent,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 1),
            "ram_total_gb": round(ram.total / (1024**3), 1),
        })

    return router
