"""
dashboard/routers/approvals.py

Spec section 19's Approval Center, as a dashboard page.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.security.approval_queue import list_pending, resolve_approval, always_allow, never_allow


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/approvals", response_class=HTMLResponse)
    def approvals_page(request: Request, message: str | None = None):
        pending = list_pending()
        return templates.TemplateResponse(request, "approvals.html", {
            "pending": pending,
            "message": message,
        })

    @router.post("/approvals/approve")
    def approve(approval_id: int = Form(...)):
        resolve_approval(approval_id, "approved")
        return RedirectResponse("/approvals?message=Approved.", status_code=303)

    @router.post("/approvals/edit")
    def edit(approval_id: int = Form(...), new_text: str = Form(...)):
        resolve_approval(approval_id, "edited", edited_payload={"draft_text": new_text})
        return RedirectResponse("/approvals?message=Approved+with+edits.", status_code=303)

    @router.post("/approvals/reject")
    def reject(approval_id: int = Form(...)):
        resolve_approval(approval_id, "rejected")
        return RedirectResponse("/approvals?message=Rejected.", status_code=303)

    @router.post("/approvals/always-allow")
    def approve_always(approval_id: int = Form(...), action_type: str = Form(...)):
        resolve_approval(approval_id, "approved")
        always_allow(action_type)
        return RedirectResponse(f"/approvals?message=Approved.+{action_type}+is+now+AUTO.", status_code=303)

    @router.post("/approvals/never-allow")
    def reject_always(approval_id: int = Form(...), action_type: str = Form(...)):
        resolve_approval(approval_id, "rejected")
        never_allow(action_type)
        return RedirectResponse(f"/approvals?message=Rejected.+{action_type}+is+now+NEVER.", status_code=303)

    return router
