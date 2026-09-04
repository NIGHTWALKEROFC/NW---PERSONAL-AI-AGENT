"""
dashboard/routers/workflows_router.py

Dashboard front-end for Phase 12 workflows — list and detail views,
plus a dry-run preview button. Exactly like automation_router.py, real
(non-dry-run) execution is intentionally NOT exposed here — only
through scripts/run_workflow_cli.py, which requires a mandatory
dry-run and an explicit typed confirmation first.

Recording a new workflow (scripts/teach_me_cli.py) also isn't exposed
here — it needs a real terminal session to capture global mouse/
keyboard input, which a web request can't do.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from database.workflow_store import list_workflows, get_workflow
from automation.desktop.workflow_executor import run_workflow


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/workflows", response_class=HTMLResponse)
    def workflows_page(request: Request):
        return templates.TemplateResponse(request, "workflows.html", {
            "workflows": list_workflows(),
        })

    @router.get("/workflows/{workflow_id}", response_class=HTMLResponse)
    def workflow_detail_page(request: Request, workflow_id: int):
        return templates.TemplateResponse(request, "workflow_detail.html", {
            "workflow": get_workflow(workflow_id),
            "dry_run_result": None,
        })

    @router.post("/workflows/{workflow_id}/dry-run", response_class=HTMLResponse)
    def workflow_dry_run(request: Request, workflow_id: int):
        workflow = get_workflow(workflow_id)
        dry_run_result = run_workflow(workflow_id, dry_run=True) if workflow else None
        return templates.TemplateResponse(request, "workflow_detail.html", {
            "workflow": workflow,
            "dry_run_result": dry_run_result,
        })

    return router
