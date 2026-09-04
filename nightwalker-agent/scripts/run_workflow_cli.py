"""
scripts/run_workflow_cli.py

List saved workflows (from Phase 12's teach-by-demonstration), preview
them via a mandatory dry-run, and only then optionally run for real —
same explicit-typed-confirmation pattern as scripts/desktop_action_cli.py.
Nothing here bypasses automation/desktop/safety_executor.py; see
automation/desktop/workflow_executor.py for the actual replay logic.

Usage:
    python scripts/run_workflow_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.workflow_store import list_workflows, get_workflow, set_status
from automation.desktop.workflow_executor import run_workflow
from automation.desktop.master_switch import is_enabled as master_switch_enabled


def print_run_result(result: dict):
    if "error" in result:
        print(f"\n[!] {result['error']}")
        return

    label = "DRY RUN" if result["dry_run"] else "REAL RUN"
    print(f"\n--- {label}: {result['workflow_name']} ---")
    for entry in result["step_results"]:
        step, res = entry["step"], entry["result"]
        print(f"  Step {entry['step_index']}: {step.get('label', step['action_type'])} -> {res['status'].upper()}")
        if res.get("reason"):
            print(f"      {res['reason']}")

    if result["halted"]:
        print(f"\n  HALTED at step {result['halted_at_step']} — {result['skipped_steps']} step(s) never attempted.")
    else:
        print(f"\n  Completed all {len(result['step_results'])} step(s) without halting.")


def main():
    workflows = list_workflows()
    if not workflows:
        print("No workflows saved yet. Use scripts/teach_me_cli.py to record one.")
        return

    print("Saved workflows:")
    for w in workflows:
        print(f"  #{w['id']}  [{w['status']}]  {w['name']}  ({len(w['steps'])} step(s))")

    try:
        workflow_id = int(input("\nWorkflow # to preview: ").strip())
    except ValueError:
        print("Not a valid workflow id.")
        return

    workflow = get_workflow(workflow_id)
    if workflow is None:
        print("No workflow with that id.")
        return

    print("\nRunning mandatory dry-run preview (no real actions, regardless of anything below)...")
    dry_result = run_workflow(workflow_id, dry_run=True)
    print_run_result(dry_result)

    if "error" in dry_result:
        return

    if dry_result["halted"]:
        print("\nThe dry-run preview itself halted partway through (e.g. a permission")
        print("is DISABLED/NEVER, or a step is missing its expected_state_description).")
        print("Fix that before considering a real run.")
        return

    if workflow["status"] != "ready":
        print(f"\nThis workflow's status is '{workflow['status']}' — only 'ready' workflows can run for real.")
        mark_ready = input("Mark it 'ready' now? [y/N]: ").strip().lower()
        if mark_ready == "y":
            set_status(workflow_id, "ready")
        else:
            return

    if not master_switch_enabled():
        print("\nDesktop automation master switch is OFF — real execution is blocked")
        print("regardless of anything else. Turn it on from the dashboard's Automation")
        print("page, or automation.desktop.master_switch.enable(), if you're sure.")
        return

    print("\nThe dry-run above shows exactly what this workflow WOULD do for real.")
    confirm = input(
        "Type 'I understand' to run it for REAL now (each step still goes through "
        "its own permission check and screen verification): "
    ).strip()
    if confirm != "I understand":
        print("Cancelled.")
        return

    real_result = run_workflow(workflow_id, dry_run=False)
    print_run_result(real_result)


if __name__ == "__main__":
    main()
