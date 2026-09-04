"""
scripts/teach_me_cli.py

The "TEACH ME" recording CLI — spec section 13's teach-by-demonstration
feature (Phase 12). Flow:

    1. Start recording (global mouse/keyboard capture via pynput).
    2. Perform the workflow manually on your machine.
    3. Press Enter in THIS terminal to stop.
    4. Review every captured step one at a time: edit typed text, add
       the expected_state_description automation needs, or redact
       anything sensitive.
    5. Save as a named workflow. It's saved with status='draft' — use
       scripts/run_workflow_cli.py to preview it and mark it 'ready'.

*** READ THIS FIRST — UNTESTED AGAINST REAL HARDWARE ***
Exactly like Phase 11's controller.py, the actual recording (real
mouse/keyboard capture) has NOT been tested against real hardware —
there is none in the sandbox this was built in. What HAS been tested:
pynput's import-time crash in this headless sandbox (confirmed — same
failure mode as pyautogui, see automation/desktop/availability.py and
automation/desktop/recorder.py's docstring), and all of the pure
event -> step conversion, redaction, and validation logic in
workflow_builder.py, using synthetic event data standing in for what a
real recording would produce. What has NOT been exercised: the real
pynput.mouse.Listener / pynput.keyboard.Listener objects actually
receiving real input from a real mouse and keyboard.

*** IMPORTANT CAVEAT: the recording is GLOBAL, not window-scoped ***
pynput's listeners capture mouse/keyboard input system-wide, not just
within whatever application you're demonstrating in. This means:
  - Pressing Enter in THIS terminal to stop the recording is itself
    captured as a keystroke event — harmless, it'll show up as a
    trailing step you can drop during review.
  - If you switch windows, type a password somewhere, or do anything
    else on your machine while a recording is running, ALL of that is
    captured in memory too — not just the workflow you intended to
    teach. Review every single step before saving; this is exactly why
    the redact option exists.

Usage:
    python scripts/teach_me_cli.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from automation.desktop.recorder import Recorder, MAX_RECORDING_SECONDS
from automation.desktop.workflow_builder import (
    build_steps_from_events,
    validate_steps,
    apply_review_edits,
)
from database.workflow_store import create_workflow


def review_steps(steps: list[dict]) -> list[dict]:
    reviewed = []
    print(f"\n{len(steps)} step(s) captured. Reviewing one at a time.\n")
    for i, step in enumerate(steps, start=1):
        print(f"--- Step {i}/{len(steps)}: {step['label']} ---")
        print(f"  action_type: {step['action_type']}")
        print(f"  params: {step['params']}")

        skip = input("  Skip this step entirely (drop it from the workflow)? [y/N]: ").strip().lower()
        if skip == "y":
            continue

        redact_answer = "n"
        if step["action_type"] == "type_text":
            redact_answer = input(
                "  Redact the typed text (e.g. it was a password or something sensitive)? [y/N]: "
            ).strip().lower()

        new_text = None
        if redact_answer != "y" and step["action_type"] == "type_text":
            edit_answer = input(
                f"  Edit the typed text? Current: {step['params']['text']!r} [y/N]: "
            ).strip().lower()
            if edit_answer == "y":
                new_text = input("  New text: ")

        expected_state = ""
        if step["action_type"] in ("click", "type_text"):
            expected_state = input(
                "  Describe what the screen should look like right before this step "
                "(required before this step can ever be run automatically): "
            ).strip()

        step = apply_review_edits(
            step,
            text=new_text,
            expected_state_description=expected_state,
            redact=(redact_answer == "y"),
        )
        reviewed.append(step)
    return reviewed


def main():
    print("=" * 60)
    print("TEACH ME — record a workflow by demonstration")
    print("This has NOT been tested against real hardware. You are the")
    print("first real test, same as scripts/desktop_action_cli.py.")
    print("=" * 60)
    print("\nRecording captures mouse/keyboard GLOBALLY (not window-scoped),")
    print("is stored in memory ONLY until you review and save it, and has a")
    print(f"hard cap of {MAX_RECORDING_SECONDS} seconds regardless of activity.")

    input("\nPress Enter to START recording...")

    recorder = Recorder()
    try:
        recorder.start()
    except Exception as e:
        print(f"\n[!] Could not start recording: {type(e).__name__}: {e}")
        print("    (Expected in a headless sandbox with no display/input devices.")
        print("    On your real Windows machine this should work; if it doesn't,")
        print("    that's new information worth telling me about.)")
        return

    print("\nRecording... perform your workflow now.")
    input("Press Enter in THIS terminal to STOP recording...\n")

    events = recorder.stop()
    print(f"Stopped. Captured {len(events)} raw event(s).")

    if not events:
        print("Nothing captured — nothing to save.")
        return

    raw_steps = build_steps_from_events(events)
    reviewed_steps = review_steps(raw_steps)

    if not reviewed_steps:
        print("\nAll steps were skipped during review — nothing to save.")
        return

    problems = validate_steps(reviewed_steps)
    if problems:
        print("\nThis workflow can still be saved as a draft, but has issues that")
        print("must be fixed before it can be run at all (even as a dry-run preview):")
        for p in problems:
            print(f"  - {p}")

    name = input("\nName this workflow: ").strip() or "Untitled workflow"
    workflow_id = create_workflow(name, reviewed_steps, status="draft")
    print(f"\nSaved as workflow #{workflow_id} ('{name}'), status=draft.")
    print("Use scripts/run_workflow_cli.py to preview (dry-run) it, mark it")
    print("'ready', and eventually run it for real.")


if __name__ == "__main__":
    main()
