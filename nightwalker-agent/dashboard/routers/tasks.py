"""
dashboard/routers/tasks.py

The TASKS/AUTOMATION dashboard sections from spec section 18, backed
by database/task_store.py (Phase 4 — storage only). The natural-
language task planner that would actually CREATE tasks from requests
like "watch this conversation and let me know if I need to respond"
is spec section 14 and does not exist yet, so this page is read-only:
nothing currently populates this table, which is stated plainly rather
than hidden.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database.task_store import list_tasks


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/tasks", response_class=HTMLResponse)
    def tasks_page(request: Request):
        tasks = list_tasks()
        return templates.TemplateResponse(request, "tasks.html", {
            "tasks": tasks,
        })

    return router
