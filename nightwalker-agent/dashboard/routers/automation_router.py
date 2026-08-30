"""
dashboard/routers/automation_router.py

The AUTOMATIONS dashboard section from spec section 18 — now real for
desktop automation specifically. Shows library availability, the
master switch, and lets you run a dry-run test from the browser.

Real (non-dry-run) execution is intentionally NOT exposed here — only
through scripts/desktop_action_cli.py, which requires typing an
explicit confirmation phrase. A one-click "run for real" button in a
web UI is exactly the kind of low-friction path to an accidental real
action that this phase's extra caution is meant to avoid, given the
underlying code has never been tested against a real display.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from automation.desktop.actions import DesktopAction, VALID_ACTION_TYPES
from automation.desktop.safety_executor import execute_action
from automation.desktop.master_switch import is_enabled, enable, disable
from automation.desktop.availability import check_all


def get_router(templates) -> APIRouter:
    router = APIRouter()

    @router.get("/automation", response_class=HTMLResponse)
    def automation_page(request: Request, message: str | None = None):
        return templates.TemplateResponse(request, "automation.html", {
            "availability": check_all(),
            "master_enabled": is_enabled(),
            "action_types": sorted(VALID_ACTION_TYPES),
            "message": message,
            "test_result": None,
        })

    @router.post("/automation/toggle-master-switch")
    def toggle_master_switch():
        if is_enabled():
            disable()
            msg = "Master+switch+turned+OFF."
        else:
            enable()
            msg = "Master+switch+turned+ON+%E2%80%94+real+actions+can+now+run+if+permitted."
        return RedirectResponse(f"/automation?message={msg}", status_code=303)

    @router.post("/automation/dry-run-test", response_class=HTMLResponse)
    def dry_run_test(
        request: Request,
        action_type: str = Form(...),
        name_or_path: str = Form(""),
        x: str = Form(""),
        y: str = Form(""),
        text: str = Form(""),
        expected_state_description: str = Form(""),
    ):
        params = {}
        if action_type == "open_app":
            params["name_or_path"] = name_or_path
        elif action_type == "click":
            params["x"] = int(x) if x else 0
            params["y"] = int(y) if y else 0
        elif action_type == "type_text":
            params["text"] = text

        try:
            action = DesktopAction(action_type=action_type, params=params, expected_state_description=expected_state_description)
            test_result = execute_action(action, dry_run=True)
        except ValueError as e:
            test_result = {"status": "error", "reason": str(e), "trace": []}

        return templates.TemplateResponse(request, "automation.html", {
            "availability": check_all(),
            "master_enabled": is_enabled(),
            "action_types": sorted(VALID_ACTION_TYPES),
            "message": None,
            "test_result": test_result,
        })

    return router
