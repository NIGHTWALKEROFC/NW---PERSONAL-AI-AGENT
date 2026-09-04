"""
automation/desktop/workflow_executor.py

run_workflow(workflow_id, dry_run=True) replays a saved workflow
(database/workflow_store.py) step by step through the EXISTING
automation/desktop/safety_executor.py — this file adds no new
execution path of its own. Every step still goes through the exact
same permission -> master switch -> screenshot -> vision verify ->
execute chain as a one-off scripts/desktop_action_cli.py action.
Nothing here calls automation/desktop/controller.py directly, and
nothing here duplicates any of safety_executor.py's decisions.

Status gating for REAL (non-dry-run) execution:
    'draft'    -> refused. Not yet marked complete/correct by the user.
    'disabled' -> refused. Explicitly turned off.
    'ready'    -> allowed, subject to every per-step check as normal.
Dry-run preview is always allowed regardless of status — it has no
side effects, and being able to preview a 'disabled' workflow (e.g. to
decide whether to re-enable it) or a 'draft' workflow (to see what
still needs fixing) is useful and safe.

Halt-on-anything-but-success: per spec section 17's failure protection
("stop, save state, log, notify — never guess or continue blindly"),
if any step's execute_action() result is not "would_execute" (dry run)
or "executed" (real run), the whole workflow stops immediately and any
remaining steps are reported as skipped — never attempted. A 6-step
workflow where step 3 is blocked/stopped/fails does NOT go on to try
steps 4-6.
"""

from automation.desktop.actions import DesktopAction
from automation.desktop.safety_executor import execute_action
from database.workflow_store import get_workflow
from agent.security.security_events import log_event

_STEP_OK_STATUSES = {"would_execute", "executed"}


def run_workflow(workflow_id: int, dry_run: bool = True) -> dict:
    """
    Returns, on success:
        {
            "workflow_id": int,
            "workflow_name": str,
            "dry_run": bool,
            "halted": bool,
            "halted_at_step": int | None,   # 1-indexed
            "step_results": [
                {"step_index": int, "step": dict, "result": dict}, ...
            ],  # one entry per step ATTEMPTED — never includes skipped steps
            "skipped_steps": int,
        }
    or {"error": str} if the workflow doesn't exist, or (for a real run
    only) isn't in a runnable status.
    """
    workflow = get_workflow(workflow_id)
    if workflow is None:
        return {"error": f"No workflow with id {workflow_id}."}

    if not dry_run and workflow["status"] != "ready":
        return {
            "error": (
                f"Workflow '{workflow['name']}' has status '{workflow['status']}' — "
                "only 'ready' workflows can run for real. A dry-run preview is always available."
            )
        }

    steps = workflow["steps"]
    step_results = []
    halted = False
    halted_at_step = None

    for i, step in enumerate(steps, start=1):
        action = DesktopAction(
            action_type=step["action_type"],
            params=step.get("params", {}),
            expected_state_description=step.get("expected_state_description", ""),
        )
        result = execute_action(action, dry_run=dry_run)
        step_results.append({"step_index": i, "step": step, "result": result})

        if result["status"] not in _STEP_OK_STATUSES:
            halted = True
            halted_at_step = i
            break

    skipped_steps = len(steps) - len(step_results)

    if not dry_run:
        log_event(
            "workflow_run",
            f"workflow_id={workflow_id} name={workflow['name']!r} "
            f"halted={halted} halted_at_step={halted_at_step} "
            f"steps_attempted={len(step_results)}/{len(steps)}",
        )

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow["name"],
        "dry_run": dry_run,
        "halted": halted,
        "halted_at_step": halted_at_step,
        "step_results": step_results,
        "skipped_steps": skipped_steps,
    }
