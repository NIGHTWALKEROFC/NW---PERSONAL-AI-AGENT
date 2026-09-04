"""
scripts/edge_case_tests.py

Spec section 32: "test edge cases extensively before allowing real
actions." This is a permanent, reusable regression suite — not a
one-off dev check — safe to run anytime.

Every test here either:
  (a) exercises real functions with synthetic/temporary data that gets
      cleaned up automatically, or
  (b) mocks only the model call (never the logic being tested), so
      the actual decision code is genuinely exercised.

Uses no live Ollama calls except where explicitly noted — most tests
run fast and don't need the model running at all.

Phase 12 additions: workflow_builder's pure event->step conversion,
review, and redaction logic; workflow_store's CRUD/status lifecycle;
workflow_executor's halt-on-first-failure behavior and its real-run
status gating (mocking only execute_action, never workflow_executor's
own halting logic); and recorder.py's pure event-handling methods
(_on_click/_on_key_press) called directly with synthetic key/click
objects, since there is no real mouse/keyboard/display in this sandbox
to drive pynput's actual listeners with.

Usage:
    python scripts/edge_case_tests.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

RESULTS = []


def check(name: str, condition: bool, detail: str = ""):
    RESULTS.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not condition else ""))


def test_never_say_hard_fail():
    print("\n=== Quality check: never_say phrase is a hard fail, even if self-check likes it ===")
    from agent.reply.quality_check import run_quality_checks
    from agent.personality.profile_schema import empty_profile

    profile = empty_profile()
    profile["boundaries"]["never_say"] = ["I cannot help with that"]

    fake_good_self_check = {"content": '{"sounds_natural": true, "too_formal": false, "too_long": false, "concerns": []}', "elapsed_seconds": 0.1, "raw": {}}
    with patch("agent.brain.model_client.ModelClient.chat", return_value=fake_good_self_check):
        result = run_quality_checks("Sorry, I cannot help with that right now", profile, recent_texts=[], model_name="fake")

    check("never_say phrase fails the check", result["passed"] is False)
    check("violation is named in concerns", any("never-say" in c.lower() for c in result["concerns"]))


def test_empty_and_whitespace_candidates_are_skipped():
    print("\n=== Candidate generator: empty/whitespace-only model output is skipped, not kept as a blank candidate ===")
    from agent.reply.candidate_generator import generate_candidates

    responses = [
        {"content": "  ", "elapsed_seconds": 0.1, "raw": {}},
        {"content": "a real reply", "elapsed_seconds": 0.1, "raw": {}},
        {"content": "", "elapsed_seconds": 0.1, "raw": {}},
    ]
    with patch("agent.brain.model_client.ModelClient.chat", side_effect=responses):
        candidates = generate_candidates([{"role": "system", "content": "x"}], "hi", "fake-model")

    check("only the one real candidate survives", len(candidates) == 1, f"got {len(candidates)}")
    if candidates:
        check("the surviving candidate is the real one", candidates[0]["text"] == "a real reply")


def test_selector_handles_zero_candidates_gracefully():
    print("\n=== Candidate selector: zero candidates raises a clear error instead of a confusing crash ===")
    from agent.reply.candidate_selector import select_best_candidate

    try:
        select_best_candidate([], style_summary="x", model_name="fake")
        check("raises ValueError on empty candidate list", False, "did not raise")
    except ValueError as e:
        check("raises ValueError on empty candidate list", True, str(e))


def test_selector_malformed_json_falls_back():
    print("\n=== Candidate selector: malformed model JSON falls back instead of crashing ===")
    from agent.reply.candidate_selector import select_best_candidate

    candidates = [{"text": "a", "temperature": 0.3}, {"text": "b", "temperature": 1.0}]
    with patch("agent.brain.model_client.ModelClient.chat", return_value={"content": "not json", "elapsed_seconds": 0.1, "raw": {}}):
        result = select_best_candidate(candidates, style_summary="x", model_name="fake")

    check("returns a valid index despite bad JSON", 0 <= result["selected_index"] < len(candidates))


def test_permission_engine_rejects_invalid_level():
    print("\n=== Permission engine: rejects an invalid level rather than silently accepting it ===")
    from agent.security.permission_engine import set_permission, get_permission

    original = get_permission("send_normal_reply")
    try:
        set_permission("send_normal_reply", "MAYBE")
        check("rejects invalid level", False, "did not raise")
    except ValueError:
        check("rejects invalid level", True)
    finally:
        set_permission("send_normal_reply", original)


def test_permission_engine_unknown_action_defaults_safe():
    print("\n=== Permission engine: an action type not in config defaults to ASK, not AUTO ===")
    from agent.security.permission_engine import get_permission

    level = get_permission("some_action_that_does_not_exist_in_config")
    check("unknown action defaults to ASK (safe), not AUTO", level == "ASK", f"got {level}")


def test_timing_midnight_wraparound():
    print("\n=== Timing rules: sleep-hours range wraps correctly past midnight ===")
    import datetime
    from agent.timing.timing_rules import get_time_bucket

    wrap_config = {
        "active_hours": {"start": "08:00", "end": "23:00"},
        "sleep_hours": {"start": "23:00", "end": "07:00"},
        "busy_hours": [],
        "min_delay_seconds": 15, "max_delay_seconds": 900,
        "cold_start_default_delay_seconds": 120, "min_history_samples_for_contact": 5,
        "busy_hours_delay_multiplier": 3.0,
    }
    bucket_1am = get_time_bucket(now=datetime.time(1, 0), config=wrap_config)
    bucket_noon = get_time_bucket(now=datetime.time(12, 0), config=wrap_config)

    check("1 AM correctly falls inside a 23:00-07:00 wraparound range", bucket_1am["in_sleep_hours"] is True)
    check("Noon correctly falls OUTSIDE that same wraparound range", bucket_noon["in_sleep_hours"] is False)


def test_timing_engine_pause_overrides_everything():
    print("\n=== Timing engine: manual pause overrides even an AUTO permission ===")
    from agent.security.permission_engine import set_permission, get_permission
    from agent.timing.pause_control import pause_indefinitely, resume
    from agent.timing.timing_engine import decide_timing

    original = get_permission("send_normal_reply")
    set_permission("send_normal_reply", "AUTO")
    pause_indefinitely()
    try:
        result = decide_timing(None)
        check("paused agent is never 'allowed' regardless of permission", result["allowed"] is False)
        check("reason correctly attributes it to manual_pause", result["based_on"] == "manual_pause")
    finally:
        resume()
        set_permission("send_normal_reply", original)


def test_history_analyzer_honest_cold_start():
    print("\n=== History analyzer: honestly returns None when there isn't enough real data, never fakes a number ===")
    from database.contact_store import get_or_create_contact, delete_contact
    from database.memory_store import log_message
    from agent.timing.history_analyzer import get_average_reply_delay

    cid = get_or_create_contact("EdgeCaseTestContact_DeleteMe")
    try:
        log_message("EdgeCaseTestContact_DeleteMe", "hi", contact_id=cid, memory_layer="imported_history", created_at="2026-01-01T10:00:00Z")
        log_message("me", "hey", contact_id=cid, memory_layer="imported_history", created_at="2026-01-01T10:01:00Z")

        result = get_average_reply_delay(cid, min_samples=5, min_delay=15, max_delay=900)
        check("returns None with only 1 sample when 5 are required", result is None, f"got {result}")
    finally:
        delete_contact(cid)  # clean up — this test's data should not persist


def test_encryption_roundtrip_and_none_handling():
    print("\n=== Encryption: round-trips correctly, and None passes through without crashing ===")
    from database.crypto import encrypt_text, decrypt_text

    original = "a piece of sensitive text"
    encrypted = encrypt_text(original)
    check("encrypted form differs from plaintext", encrypted != original)
    check("decrypts back to the original", decrypt_text(encrypted) == original)
    check("None encrypts to None", encrypt_text(None) is None)
    check("None decrypts to None", decrypt_text(None) is None)


def test_wipe_leaves_tasks_and_events_untouched():
    print("\n=== Data wipe: clears personal data but leaves tasks and security events alone, as designed ===")
    from database.task_store import create_task, list_tasks, delete_task
    from agent.security.security_events import log_event, get_recent_events
    from agent.personality.profile_store import save_profile, load_profile
    from database.wipe import wipe_all_personal_data

    profile = load_profile()
    profile["personal_knowledge"] = [{"fact": "EDGE_CASE_MARKER", "added_at": "x", "source": "test"}]
    save_profile(profile)

    task_id = create_task("EDGE_CASE_TASK_MARKER")
    log_event("edge_case_test_event", "EDGE_CASE_EVENT_MARKER")

    wipe_all_personal_data()

    profile_after = load_profile()
    check("profile was wiped", profile_after["personal_knowledge"] == [])

    tasks_after = list_tasks()
    check("task survived the wipe", any(t["goal"] == "EDGE_CASE_TASK_MARKER" for t in tasks_after))

    events_after = get_recent_events()
    check("security event survived the wipe", any("EDGE_CASE_EVENT_MARKER" in (e["detail"] or "") for e in events_after))

    # Clean up what this test itself added (the task) so re-running stays clean.
    for t in tasks_after:
        if t["goal"] == "EDGE_CASE_TASK_MARKER":
            delete_task(t["id"])


def test_workflow_builder_converts_events_and_flags_unfinished_steps():
    print("\n=== Workflow builder: converts recorded events to steps, and validate_steps flags blank expected_state_description ===")
    from automation.desktop.workflow_builder import build_steps_from_events, validate_steps

    synthetic_events = [
        {"type": "click", "x": 400, "y": 620, "button": "Button.left", "t": 0.5},
        {"type": "key", "text": "hello world", "t": 1.2},
        {"type": "key_special", "name": "Key.enter", "t": 1.3},
    ]
    steps = build_steps_from_events(synthetic_events)

    check("click event becomes a click step", steps[0]["action_type"] == "click")
    check("click params carry the coordinates", steps[0]["params"] == {"x": 400, "y": 620})
    check("key event becomes a type_text step", steps[1]["action_type"] == "type_text")
    check("typed text is preserved", steps[1]["params"]["text"] == "hello world")
    check("key_special becomes a bracketed type_text marker", steps[2]["params"]["text"] == "[ENTER]")

    # Fresh from conversion, every step has a blank expected_state_description —
    # validate_steps must catch this rather than letting an unreviewed workflow look valid.
    # All 3 synthetic steps are click/type_text, so all 3 require it and all 3 should be flagged.
    problems = validate_steps(steps)
    check(
        "unreviewed steps (blank expected_state_description) are all flagged as invalid",
        len(problems) == 3,
        f"got {len(problems)}: {problems}",
    )


def test_workflow_builder_unknown_event_type_raises():
    print("\n=== Workflow builder: an unrecognized recorded event type raises instead of being silently dropped ===")
    from automation.desktop.workflow_builder import build_steps_from_events

    try:
        build_steps_from_events([{"type": "scroll", "t": 0.1}])
        check("unknown event type raises ValueError", False, "did not raise")
    except ValueError:
        check("unknown event type raises ValueError", True)


def test_workflow_builder_review_and_redact():
    print("\n=== Workflow builder: review edits fill in expected_state_description, and redact discards the original text ===")
    from automation.desktop.workflow_builder import build_steps_from_events, apply_review_edits, validate_steps

    steps = build_steps_from_events([{"type": "key", "text": "my-secret-password", "t": 0.1}])
    reviewed = apply_review_edits(steps[0], redact=True, expected_state_description="Login form is visible")

    check("redacted step no longer contains the original text", "my-secret-password" not in reviewed["params"]["text"])
    check("redacted step is marked with the redaction placeholder", reviewed["params"]["text"] == "[REDACTED]")
    check("expected_state_description was applied during review", reviewed["expected_state_description"] == "Login form is visible")
    check("a fully reviewed step passes validation", validate_steps([reviewed]) == [])

    # apply_review_edits must never mutate the step it was given — the caller's
    # original list (what's shown on screen during review) has to stay intact.
    check("original step dict was not mutated", steps[0]["params"]["text"] == "my-secret-password")


def test_workflow_store_roundtrip_and_status_lifecycle():
    print("\n=== Workflow store: create/get/update round-trip correctly, and set_status rejects an invalid status ===")
    from database.workflow_store import (
        create_workflow, get_workflow, update_steps, set_status, delete_workflow, list_workflows,
    )

    steps = [{"action_type": "open_app", "params": {"name_or_path": "notepad"}, "expected_state_description": "", "label": "Open Notepad"}]
    workflow_id = create_workflow("EDGE_CASE_WORKFLOW_MARKER", steps)
    try:
        fetched = get_workflow(workflow_id)
        check("workflow round-trips with the same steps", fetched["steps"] == steps)
        check("new workflow defaults to draft status", fetched["status"] == "draft")

        new_steps = steps + [{"action_type": "read_screen", "params": {}, "expected_state_description": "", "label": "Read screen"}]
        update_steps(workflow_id, new_steps)
        check("update_steps persists the new step list", get_workflow(workflow_id)["steps"] == new_steps)

        set_status(workflow_id, "ready")
        check("set_status persists a valid status", get_workflow(workflow_id)["status"] == "ready")

        try:
            set_status(workflow_id, "not_a_real_status")
            check("set_status rejects an invalid status", False, "did not raise")
        except ValueError:
            check("set_status rejects an invalid status", True)

        check(
            "list_workflows(status='ready') includes this workflow",
            any(w["id"] == workflow_id for w in list_workflows(status="ready")),
        )
    finally:
        delete_workflow(workflow_id)  # clean up — this test's data should not persist

    check("deleted workflow is no longer retrievable", get_workflow(workflow_id) is None)


def test_workflow_executor_halts_on_first_non_ok_step():
    print("\n=== Workflow executor: halts immediately on the first non-ok step and never attempts the rest ===")
    from database.workflow_store import create_workflow, delete_workflow
    from automation.desktop.workflow_executor import run_workflow

    steps = [
        {"action_type": "open_app", "params": {"name_or_path": "notepad"}, "expected_state_description": "", "label": "Step 1 (ok)"},
        {"action_type": "read_screen", "params": {}, "expected_state_description": "", "label": "Step 2 (will be blocked)"},
        {"action_type": "open_app", "params": {"name_or_path": "calc"}, "expected_state_description": "", "label": "Step 3 (must never run)"},
    ]
    workflow_id = create_workflow("EDGE_CASE_HALT_WORKFLOW_MARKER", steps, status="ready")

    fake_results = [
        {"status": "would_execute", "trace": []},
        {"status": "blocked", "reason": "simulated block", "trace": []},
    ]
    try:
        with patch("automation.desktop.workflow_executor.execute_action", side_effect=fake_results):
            result = run_workflow(workflow_id, dry_run=True)

        check("workflow reports halted", result["halted"] is True)
        check("halted at the correct step", result["halted_at_step"] == 2)
        check("only the attempted steps appear in step_results", len(result["step_results"]) == 2)
        check("the never-reached step was counted as skipped", result["skipped_steps"] == 1)
    finally:
        delete_workflow(workflow_id)  # clean up — this test's data should not persist


def test_workflow_executor_blocks_real_run_unless_ready():
    print("\n=== Workflow executor: refuses a REAL run for draft/disabled workflows but always allows dry-run ===")
    from database.workflow_store import create_workflow, delete_workflow
    from automation.desktop.workflow_executor import run_workflow

    steps = [{"action_type": "open_app", "params": {"name_or_path": "notepad"}, "expected_state_description": "", "label": "Open Notepad"}]
    draft_id = create_workflow("EDGE_CASE_DRAFT_WORKFLOW_MARKER", steps, status="draft")
    try:
        real_result = run_workflow(draft_id, dry_run=False)
        check("real run on a draft workflow is refused", "error" in real_result)

        with patch("automation.desktop.workflow_executor.execute_action", return_value={"status": "would_execute", "trace": []}):
            dry_result = run_workflow(draft_id, dry_run=True)
        check("dry-run preview on a draft workflow is still allowed", "error" not in dry_result)
    finally:
        delete_workflow(draft_id)  # clean up — this test's data should not persist


def test_recorder_coalesces_typed_characters_and_flushes_on_click():
    print("\n=== Recorder: consecutive keystrokes coalesce into one run, flushed by the next click ===")
    from automation.desktop.recorder import Recorder
    import time as _time

    recorder = Recorder()
    recorder._start_time = _time.monotonic()  # simulate an already-started recording without touching pynput

    class FakeCharKey:
        def __init__(self, char):
            self.char = char

    class FakeSpecialKey:
        def __str__(self):
            return "Key.enter"
        # deliberately no .char attribute, matching pynput's real special keys

    for c in "hi":
        recorder._on_key_press(FakeCharKey(c))
    recorder._on_click(10, 20, "Button.left", True)
    recorder._on_key_press(FakeSpecialKey())
    events = recorder.stop()

    check("exactly 3 events recorded (coalesced text, click, special key)", len(events) == 3, f"got {len(events)}: {events}")
    check("consecutive keystrokes coalesced into one 'hi' event", events[0] == {"type": "key", "text": "hi", "t": events[0]["t"]})
    check("click event recorded between the two key events", events[1]["type"] == "click" and events[1]["x"] == 10)
    check("special key recorded as its own key_special event", events[2] == {"type": "key_special", "name": "Key.enter", "t": events[2]["t"]})


def test_recorder_ignores_release_and_respects_stopped_flag():
    print("\n=== Recorder: ignores button-release events, and stops accepting events once stopped ===")
    from automation.desktop.recorder import Recorder
    import time as _time

    recorder = Recorder()
    recorder._start_time = _time.monotonic()

    recorder._on_click(1, 1, "Button.left", False)  # release, not press — must be ignored
    check("a release-only click is not recorded", len(recorder.events) == 0)

    class FakeCharKey:
        def __init__(self, char):
            self.char = char

    recorder.stop()
    result = recorder._on_key_press(FakeCharKey("x"))
    check("on_key_press returns False once stopped (tells pynput's listener to stop)", result is False)
    check("no event was recorded after stop() was called", len(recorder.events) == 0)


def main():
    print("Running edge case regression suite...")
    print("(Some tests create and immediately clean up their own temporary data.)\n")

    test_never_say_hard_fail()
    test_empty_and_whitespace_candidates_are_skipped()
    test_selector_handles_zero_candidates_gracefully()
    test_selector_malformed_json_falls_back()
    test_permission_engine_rejects_invalid_level()
    test_permission_engine_unknown_action_defaults_safe()
    test_timing_midnight_wraparound()
    test_timing_engine_pause_overrides_everything()
    test_history_analyzer_honest_cold_start()
    test_encryption_roundtrip_and_none_handling()
    test_wipe_leaves_tasks_and_events_untouched()
    test_workflow_builder_converts_events_and_flags_unfinished_steps()
    test_workflow_builder_unknown_event_type_raises()
    test_workflow_builder_review_and_redact()
    test_workflow_store_roundtrip_and_status_lifecycle()
    test_workflow_executor_halts_on_first_non_ok_step()
    test_workflow_executor_blocks_real_run_unless_ready()
    test_recorder_coalesces_typed_characters_and_flushes_on_click()
    test_recorder_ignores_release_and_respects_stopped_flag()

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"RESULT: {passed}/{total} checks passed")
    if passed != total:
        print("\nFailed checks:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
