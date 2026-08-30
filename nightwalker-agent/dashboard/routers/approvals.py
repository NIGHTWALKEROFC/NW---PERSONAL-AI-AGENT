"""
dashboard/routers/approvals.py

Spec section 19's Approval Center, as a dashboard page.

Phase 10 update: approving or editing now actually sends the message
via the real platform connector (agent/actions/action_dispatcher.py).
If the send fails (missing platform info, connector not configured,
API error), the approval is still marked resolved but the flash
message tells you plainly that sending failed — never silently
pretends success.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from agent.security.approval_queue import list_pending, resolve_approval, always_allow, never_allow, get_approval
from agent.actions.action_dispatcher import dispatch_send, DispatchError


def _try_send(approval_id: int, text: str) -> str:
    """Returns a status suffix for the flash message describing what actually happened."""
    item = get_approval(approval_id)
    if item is None or item.get("contact_id") is None:
        return "+(no+contact+on+record+%E2%80%94+nothing+sent)"
    try:
        dispatch_send(item["contact_id"], text)
        return "+and+sent."
    except DispatchError as e:
        return f"+but+SENDING+FAILED:+{str(e)[:80]}"


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
        item = get_approval(approval_id)
        text = item["payload"].get("draft_text", "") if item else ""
        resolve_approval(approval_id, "approved")
        suffix = _try_send(approval_id, text)
        return RedirectResponse(f"/approvals?message=Approved{suffix}", status_code=303)

    @router.post("/approvals/edit")
    def edit(approval_id: int = Form(...), new_text: str = Form(...)):
        resolve_approval(approval_id, "edited", edited_payload={"draft_text": new_text})
        suffix = _try_send(approval_id, new_text)
        return RedirectResponse(f"/approvals?message=Approved+with+edits{suffix}", status_code=303)

    @router.post("/approvals/reject")
    def reject(approval_id: int = Form(...)):
        resolve_approval(approval_id, "rejected")
        return RedirectResponse("/approvals?message=Rejected.+Nothing+sent.", status_code=303)

    @router.post("/approvals/always-allow")
    def approve_always(approval_id: int = Form(...), action_type: str = Form(...)):
        item = get_approval(approval_id)
        text = item["payload"].get("draft_text", "") if item else ""
        resolve_approval(approval_id, "approved")
        always_allow(action_type)
        suffix = _try_send(approval_id, text)
        return RedirectResponse(f"/approvals?message=Approved{suffix}+{action_type}+is+now+AUTO.", status_code=303)

    @router.post("/approvals/never-allow")
    def reject_always(approval_id: int = Form(...), action_type: str = Form(...)):
        resolve_approval(approval_id, "rejected")
        never_allow(action_type)
        return RedirectResponse(f"/approvals?message=Rejected.+Nothing+sent.+{action_type}+is+now+NEVER.", status_code=303)

    return router
