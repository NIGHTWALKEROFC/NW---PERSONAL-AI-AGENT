"""
automation/desktop/safety_executor.py

Implements spec sections 12/16/17's core safety flow for every desktop
action:

    permission check -> master switch check -> screenshot ->
    vision verification -> execute (or STOP)

    on ANY exception or mismatch:
        STOP -> LOG -> return failure (never continue, never guess)

This is the one function everything else in this phase funnels
through. Nothing calls automation/desktop/controller.py directly
except this file.

Every step here IS tested (permission gating, master switch gating,
screenshot-unavailable handling, mismatch handling, exception handling)
using a mocked controller — because the actual controller functions
themselves cannot be exercised without a real display. See this
package's other files for exactly what has and hasn't been verified.
"""

from automation.desktop.actions import DesktopAction, REQUIRES_VERIFICATION
from automation.desktop.screen_capture import capture_screenshot
from automation.desktop.vision_verifier import check_match
from automation.desktop.master_switch import is_enabled as master_switch_enabled
from automation.desktop import controller
from agent.security.permission_engine import get_permission
from agent.security.approval_queue import create_approval
from agent.security.security_events import log_event

_ACTION_EXECUTORS = {
    "open_app": lambda action: controller.open_application(action.params.get("name_or_path", "")),
    "click": lambda action: controller.click(action.params.get("x", 0), action.params.get("y", 0)),
    "type_text": lambda action: controller.type_text(action.params.get("text", "")),
    "read_screen": lambda action: controller.list_open_windows(),  # placeholder low-risk "read" until OCR/vision describe is wired to a real use
}


def execute_action(action: DesktopAction, dry_run: bool = True) -> dict:
    """
    Returns a dict with at least {"status": str, "trace": list[str]}.

    status is one of:
        "would_execute"    (dry_run only — nothing real happened)
        "blocked"          (permission or master switch says no)
        "pending_approval" (permission is ASK — a real approval was queued, not executed)
        "stopped"          (screen verification failed or was unavailable for a real action)
        "executed"         (the action actually ran, and succeeded)
        "failed"           (the action actually ran and raised/reported an error)
    """
    trace = []

    permission_key = action.permission_key()
    level = get_permission(permission_key)
    trace.append(f"permission[{permission_key}] = {level}")

    if level in ("DISABLED", "NEVER"):
        return {"status": "blocked", "reason": f"Permission level is {level}.", "trace": trace}

    if not dry_run and not master_switch_enabled():
        trace.append("master switch is OFF")
        return {
            "status": "blocked",
            "reason": "Desktop automation master switch is OFF — enable it explicitly before real actions can run.",
            "trace": trace,
        }

    if level == "ASK" and not dry_run:
        approval_id = create_approval(
            action_type=permission_key,
            payload={"action_type": action.action_type, "params": action.params},
            reasoning=action.expected_state_description or "(no verification description provided)",
        )
        trace.append(f"permission is ASK — created approval id {approval_id} instead of executing")
        return {"status": "pending_approval", "approval_id": approval_id, "trace": trace}

    screenshot = capture_screenshot()
    trace.append(f"screenshot available: {screenshot['available']}" + (f" ({screenshot['error']})" if not screenshot["available"] else ""))

    if action.action_type in REQUIRES_VERIFICATION:
        if not screenshot["available"]:
            log_event("desktop_automation_stopped", f"screenshot unavailable for {action.action_type}: {screenshot['error']}")
            return {
                "status": "stopped",
                "reason": "Cannot verify screen state (screenshot capture unavailable) — refusing to act blindly.",
                "trace": trace,
            }

        verification = check_match(screenshot["path"], action.expected_state_description)
        trace.append(f"verification available={verification['available']}, matches={verification['matches_expected']}: {verification['description']}")

        if not verification["available"] or not verification["matches_expected"]:
            log_event(
                "desktop_automation_stopped",
                f"verification failed for {action.action_type}: {verification['description']}",
            )
            return {
                "status": "stopped",
                "reason": f"Screen did not match expectation: {verification['description']}",
                "trace": trace,
            }

    if dry_run:
        trace.append("dry_run=True — nothing real executed")
        return {"status": "would_execute", "trace": trace}

    executor = _ACTION_EXECUTORS.get(action.action_type)
    try:
        result = executor(action)
    except Exception as e:
        log_event("desktop_action_failed", f"{action.action_type}: {type(e).__name__}: {e}")
        return {"status": "failed", "reason": f"Unexpected exception: {type(e).__name__}: {e}", "trace": trace}

    if not result.get("success"):
        log_event("desktop_action_failed", f"{action.action_type}: {result.get('error')}")
        return {"status": "failed", "reason": result.get("error"), "trace": trace}

    log_event("desktop_action_executed", f"{action.action_type}: {action.params}")
    return {"status": "executed", "result": result, "trace": trace}
