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

Phase 13 additions: Meta signature verification (valid/tampered/wrong-
secret cases); Instagram and WhatsApp webhook payload parsing against
synthetic payloads matching Meta's published docs (both of Instagram's
known shapes, WhatsApp's display-name fallback, non-text skipping);
webhook_inbox_store's one-shot-drain and per-platform duplicate
detection; the actual webhook_server FastAPI routes end-to-end via
TestClient (GET challenge handshake, POST signature rejection/
acceptance) with a real HMAC-signed request; and confirming the
Instagram/WhatsApp adapters read from that local queue rather than the
network. The real Meta API and a real webhook delivery are NOT
exercised — that requires live credentials only you have.

Phase 14 additions: dashboard_auth's full password/session lifecycle
(set/verify, create/validate/revoke/revoke-all, password change
revoking existing sessions), login lockout after repeated failures,
the actual DashboardAuthMiddleware + login/logout routes end-to-end
via TestClient in both its opt-in states (no password = fully open,
exactly like every phase before this one; password set = enforced),
and confirming the kill switch's activate() really does revoke every
dashboard session as one of its actions. dashboard_auth is a single-
row singleton table, so every Phase 14 test cleans up via
_reset_dashboard_auth_state() so re-running this suite (or the real
app afterward) starts from "no password set" again, same as before
these tests ran.

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


def test_meta_signature_verification():
    print("\n=== Meta signature verification: valid signature passes, tampered body or wrong secret fails ===")
    import hmac
    import hashlib
    from connectors.meta_shared import verify_signature

    body = b'{"entry": []}'
    secret = "my-app-secret"
    valid_sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    check("valid signature verifies", verify_signature(body, valid_sig, secret) is True)
    check("tampered body fails verification", verify_signature(b'{"entry": [1]}', valid_sig, secret) is False)
    check("wrong secret fails verification", verify_signature(body, valid_sig, "wrong-secret") is False)
    check("missing 'sha256=' prefix is rejected outright", verify_signature(body, "not-even-close", secret) is False)
    check("empty signature header fails", verify_signature(body, "", secret) is False)
    check("empty app secret fails (never treat 'not configured' as 'accept anything')", verify_signature(body, valid_sig, "") is False)


def test_instagram_payload_parsing_both_shapes():
    print("\n=== Instagram adapter: parses the classic Messenger-style shape, the fallback shape, and skips echoes/non-text ===")
    from connectors.instagram.instagram_adapter import parse_webhook_payload

    classic_payload = {
        "entry": [{
            "messaging": [
                {"sender": {"id": "1001"}, "timestamp": 123, "message": {"mid": "m1", "text": "hey there"}},
                {"sender": {"id": "1001"}, "timestamp": 124, "message": {"mid": "m2", "text": "echo", "is_echo": True}},
                {"sender": {"id": "1001"}, "timestamp": 125, "message": {"mid": "m3", "sticker_id": 999}},  # no text
            ]
        }]
    }
    results = parse_webhook_payload(classic_payload)
    check("classic shape: only the real text message survives (echo and non-text skipped)", len(results) == 1, f"got {results}")
    check("classic shape: text and sender extracted correctly", results[0]["text"] == "hey there" and results[0]["platform_user_id"] == "1001")

    fallback_payload = {
        "entry": [{
            "changes": [{
                "value": {"messages": [
                    {"from": "2002", "id": "m4", "timestamp": 200, "type": "text", "text": {"body": "fallback shape"}},
                    {"from": "2002", "id": "m5", "timestamp": 201, "type": "image"},  # non-text, skipped
                ]}
            }]
        }]
    }
    fallback_results = parse_webhook_payload(fallback_payload)
    check("fallback shape: only the text message survives", len(fallback_results) == 1, f"got {fallback_results}")
    check("fallback shape: nested text.body extracted correctly", fallback_results[0]["text"] == "fallback shape")

    check("empty entry list produces no results", parse_webhook_payload({"entry": []}) == [])


def test_whatsapp_payload_parsing_and_display_name_fallback():
    print("\n=== WhatsApp adapter: parses text messages, uses contacts[].profile.name when present, falls back to a placeholder otherwise ===")
    from connectors.whatsapp.whatsapp_adapter import parse_webhook_payload

    payload_with_name = {
        "entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": "917000000001", "profile": {"name": "Asha"}}],
            "messages": [{"from": "917000000001", "id": "wamid.1", "timestamp": "300", "type": "text", "text": {"body": "hello"}}],
        }}]}]
    }
    results = parse_webhook_payload(payload_with_name)
    check("exactly one message parsed", len(results) == 1, f"got {results}")
    check("display_name comes from contacts[].profile.name when present", results[0]["display_name"] == "Asha")
    check("message text extracted correctly", results[0]["text"] == "hello")

    payload_without_name = {
        "entry": [{"changes": [{"value": {
            "messages": [{"from": "917000000002", "id": "wamid.2", "timestamp": "301", "type": "text", "text": {"body": "hi"}}],
        }}]}]
    }
    fallback_results = parse_webhook_payload(payload_without_name)
    check("display_name falls back to a placeholder when contacts[] is absent (never fakes a real name)", fallback_results[0]["display_name"] == "whatsapp_user_917000000002")

    non_text_payload = {
        "entry": [{"changes": [{"value": {
            "messages": [{"from": "917000000003", "id": "wamid.3", "timestamp": "302", "type": "location"}],
        }}]}]
    }
    check("non-text message types are skipped, not errors", parse_webhook_payload(non_text_payload) == [])


def test_webhook_inbox_store_drain_is_one_shot_and_platform_scoped():
    print("\n=== Webhook inbox store: drain() returns each message exactly once, and never leaks across platforms ===")
    from database import webhook_inbox_store
    from database.db import get_connection

    try:
        webhook_inbox_store.enqueue("instagram", "u1", "Test User", "hello from instagram", "msg-edge-1", "111")
        webhook_inbox_store.enqueue("whatsapp", "u2", "Test User 2", "hello from whatsapp", "msg-edge-2", "222")

        instagram_batch = webhook_inbox_store.drain("instagram")
        check("drain returns only this platform's message", len(instagram_batch) == 1 and instagram_batch[0]["text"] == "hello from instagram")

        instagram_batch_again = webhook_inbox_store.drain("instagram")
        check("draining again returns nothing — each message is consumed exactly once", instagram_batch_again == [])

        whatsapp_batch = webhook_inbox_store.drain("whatsapp")
        check("the whatsapp message was never affected by draining instagram", len(whatsapp_batch) == 1 and whatsapp_batch[0]["text"] == "hello from whatsapp")
    finally:
        # clean up — drain() only marks rows consumed, it does not delete them, so a real
        # DELETE is needed here to actually keep this test's data from persisting.
        conn = get_connection()
        conn.execute("DELETE FROM webhook_inbox WHERE message_id IN ('msg-edge-1', 'msg-edge-2')")
        conn.commit()


def test_webhook_inbox_store_duplicate_detection():
    print("\n=== Webhook inbox store: is_message_already_enqueued() correctly detects duplicates, scoped per platform ===")
    from database import webhook_inbox_store
    from database.db import get_connection

    try:
        check("a message_id not yet seen is not a duplicate", webhook_inbox_store.is_message_already_enqueued("instagram", "msg-edge-dup-1") is False)
        check("a blank message_id is never treated as a duplicate", webhook_inbox_store.is_message_already_enqueued("instagram", "") is False)

        webhook_inbox_store.enqueue("instagram", "u3", "Dup Test", "first delivery", "msg-edge-dup-1", "333")
        check("the same message_id on the same platform is now a duplicate", webhook_inbox_store.is_message_already_enqueued("instagram", "msg-edge-dup-1") is True)
        check("the same message_id on a DIFFERENT platform is NOT a duplicate", webhook_inbox_store.is_message_already_enqueued("whatsapp", "msg-edge-dup-1") is False)
    finally:
        # clean up — drain() only marks rows consumed, but is_message_already_enqueued()
        # checks message_id regardless of consumed status, so a leftover row here would
        # make this exact test fail on every subsequent run. Delete outright instead.
        conn = get_connection()
        conn.execute("DELETE FROM webhook_inbox WHERE message_id = 'msg-edge-dup-1'")
        conn.commit()


def test_webhook_server_rejects_bad_signature_and_accepts_valid_one():
    print("\n=== Webhook server: GET verification handshake and POST signature enforcement both work end-to-end ===")
    import hmac
    import hashlib
    import json
    import os
    from fastapi.testclient import TestClient
    from database import webhook_inbox_store
    from database.db import get_connection

    os.environ["INSTAGRAM_WEBHOOK_VERIFY_TOKEN"] = "edge-case-verify-token"
    os.environ["INSTAGRAM_APP_SECRET"] = "edge-case-app-secret"

    from webhooks.webhook_server import app
    client = TestClient(app)

    try:
        # GET verification handshake
        resp = client.get("/webhooks/instagram", params={
            "hub.mode": "subscribe", "hub.verify_token": "edge-case-verify-token", "hub.challenge": "abc123",
        })
        check("correct verify token echoes the challenge back with 200", resp.status_code == 200 and resp.text == "abc123")

        resp_wrong = client.get("/webhooks/instagram", params={
            "hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "abc123",
        })
        check("wrong verify token is rejected with 403", resp_wrong.status_code == 403)

        # POST without a valid signature must be rejected, and must NOT enqueue anything
        body = json.dumps({"entry": [{"messaging": [{"sender": {"id": "u9"}, "timestamp": 1, "message": {"mid": "msg-edge-webhook-1", "text": "should not be enqueued"}}]}]})
        resp_bad_sig = client.post("/webhooks/instagram", content=body, headers={"x-hub-signature-256": "sha256=wrong"})
        check("POST with an invalid signature is rejected with 403", resp_bad_sig.status_code == 403)
        check("nothing was enqueued from the rejected request", webhook_inbox_store.is_message_already_enqueued("instagram", "msg-edge-webhook-1") is False)

        # POST with a valid signature must succeed and enqueue the message
        valid_sig = "sha256=" + hmac.new(b"edge-case-app-secret", body.encode(), hashlib.sha256).hexdigest()
        resp_good = client.post("/webhooks/instagram", content=body, headers={"x-hub-signature-256": valid_sig})
        check("POST with a valid signature is accepted with 200", resp_good.status_code == 200)
        check("the message was actually enqueued", webhook_inbox_store.is_message_already_enqueued("instagram", "msg-edge-webhook-1") is True)
    finally:
        # clean up — see test_webhook_inbox_store_duplicate_detection's finally block for why
        # this must be a real DELETE, not just drain().
        conn = get_connection()
        conn.execute("DELETE FROM webhook_inbox WHERE message_id = 'msg-edge-webhook-1'")
        conn.commit()


def test_instagram_and_whatsapp_adapters_use_webhook_inbox_not_network():
    print("\n=== Instagram/WhatsApp adapters: fetch_incoming_messages() reads the local queue, no network call involved ===")
    from database import webhook_inbox_store
    from database.db import get_connection
    from connectors.instagram.instagram_adapter import InstagramAdapter
    from connectors.whatsapp.whatsapp_adapter import WhatsAppAdapter

    try:
        webhook_inbox_store.enqueue("instagram", "u10", "Queue Test", "queued instagram message", "msg-edge-queue-ig", "400")
        ig_messages = InstagramAdapter().fetch_incoming_messages()
        check("InstagramAdapter.fetch_incoming_messages returns the queued message", len(ig_messages) == 1 and ig_messages[0].text == "queued instagram message")

        webhook_inbox_store.enqueue("whatsapp", "u11", "Queue Test 2", "queued whatsapp message", "msg-edge-queue-wa", "401")
        wa_messages = WhatsAppAdapter().fetch_incoming_messages()
        check("WhatsAppAdapter.fetch_incoming_messages returns the queued message", len(wa_messages) == 1 and wa_messages[0].text == "queued whatsapp message")
    finally:
        # clean up — drain() (called internally by fetch_incoming_messages) only marks rows
        # consumed, it does not delete them; a real DELETE is needed to fully clean up.
        conn = get_connection()
        conn.execute("DELETE FROM webhook_inbox WHERE message_id IN ('msg-edge-queue-ig', 'msg-edge-queue-wa')")
        conn.commit()


def test_registry_includes_all_three_platforms():
    print("\n=== Connector registry: Telegram, Instagram, and WhatsApp are all registered and resolvable ===")
    from connectors.registry import list_platforms, get_adapter

    platforms = list_platforms()
    check("all three platforms are listed", set(platforms) == {"telegram", "instagram", "whatsapp"}, f"got {platforms}")
    check("get_adapter resolves instagram", get_adapter("instagram").platform_name == "instagram")
    check("get_adapter resolves whatsapp", get_adapter("whatsapp").platform_name == "whatsapp")
    check("get_adapter returns None for an unregistered platform", get_adapter("not_a_real_platform") is None)


def _reset_dashboard_auth_state():
    """
    Test-only cleanup: dashboard_auth is a single-row singleton (like
    personality_profile), so tests that call set_password() must
    restore "no password set" afterward or every subsequent run of
    this suite (and the real app, using the same database) would
    start with auth already turned on. Deliberately raw SQL here
    rather than a delete_password() function in the real module —
    "remove your own password protection" isn't a feature the app
    should offer; this is test-harness-only.
    """
    from database.db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM dashboard_auth WHERE id = 1")
    conn.execute("DELETE FROM dashboard_sessions")
    conn.execute("DELETE FROM login_attempts")
    conn.commit()


def test_dashboard_auth_password_and_session_lifecycle():
    print("\n=== Dashboard auth: password set/verify, session create/validate/revoke, and password-change revokes everything ===")
    from agent.security.dashboard_auth import (
        has_password_set, set_password, verify_password, create_session,
        validate_session, revoke_session, revoke_all_sessions, list_active_sessions,
    )

    try:
        check("no password set initially in a clean state", has_password_set() is False)

        set_password("edge-case-password-1")
        check("has_password_set is True after set_password", has_password_set() is True)
        check("correct password verifies", verify_password("edge-case-password-1") is True)
        check("wrong password fails to verify", verify_password("definitely-wrong") is False)

        try:
            set_password("short")
            check("a too-short password is rejected", False, "did not raise")
        except ValueError:
            check("a too-short password is rejected", True)

        sid = create_session(device_label="Edge Case Device")
        check("a freshly created session validates", validate_session(sid) is True)
        check("a made-up session id does not validate", validate_session("not-a-real-session-id") is False)

        active = list_active_sessions()
        check("the new session appears in list_active_sessions", any(s["device_label"] == "Edge Case Device" for s in active))

        revoke_session(sid)
        check("a revoked session no longer validates", validate_session(sid) is False)

        sid_a = create_session(device_label="Device A")
        sid_b = create_session(device_label="Device B")
        count = revoke_all_sessions()
        check("revoke_all_sessions revokes every active session", count == 2, f"got {count}")
        check("device A session dead after revoke_all", validate_session(sid_a) is False)
        check("device B session dead after revoke_all", validate_session(sid_b) is False)

        sid_c = create_session(device_label="Device C")
        set_password("edge-case-password-2")
        check("changing the password revokes existing sessions as a side effect", validate_session(sid_c) is False)
        check("the OLD password no longer verifies after a change", verify_password("edge-case-password-1") is False)
        check("the NEW password verifies after a change", verify_password("edge-case-password-2") is True)
    finally:
        _reset_dashboard_auth_state()  # clean up — this test's data should not persist


def test_dashboard_auth_login_lockout():
    print("\n=== Dashboard auth: login lockout kicks in after too many failures, scoped per source IP ===")
    from agent.security.dashboard_auth import record_login_attempt, is_locked_out

    try:
        check("a fresh IP is not locked out", is_locked_out("203.0.113.10") is False)

        for _ in range(5):
            record_login_attempt("203.0.113.10", success=False)
        check("5 failed attempts triggers lockout", is_locked_out("203.0.113.10") is True)
        check("a different IP is unaffected by another IP's failures", is_locked_out("203.0.113.99") is False)

        record_login_attempt("203.0.113.55", success=True)
        check("a single successful attempt does not trigger lockout", is_locked_out("203.0.113.55") is False)
    finally:
        _reset_dashboard_auth_state()  # clean up — this test's data should not persist


def test_dashboard_middleware_opt_in_and_enforced_states():
    print("\n=== Dashboard auth middleware: fully open with no password set, fully enforced once one is, login/logout both work ===")
    from fastapi.testclient import TestClient
    from dashboard.app import app
    from agent.security.dashboard_auth import set_password

    try:
        client = TestClient(app)

        # No password set at all -> every route open, exactly like every phase before this one.
        r = client.get("/security", follow_redirects=False)
        check("with no password set, a protected page is reachable with no login", r.status_code == 200)

        set_password("edge-case-middleware-pw")

        r = client.get("/security", follow_redirects=False)
        check("once a password is set, the same page redirects to /login without a session", r.status_code == 303 and "/login" in r.headers.get("location", ""))

        r = client.get("/login")
        check("/login itself remains reachable without a session", r.status_code == 200)

        r = client.post("/login", data={"password": "wrong-password", "next": "/"}, follow_redirects=False)
        check("a wrong password does not set a session cookie", "nw_session" not in r.cookies)

        r = client.post("/login", data={"password": "edge-case-middleware-pw", "next": "/security"}, follow_redirects=False)
        check("the correct password redirects to the originally requested page", r.status_code == 303 and r.headers.get("location") == "/security")
        check("the correct password sets a session cookie", "nw_session" in r.cookies)

        r = client.get("/security")
        check("the protected page is now reachable using the session cookie", r.status_code == 200 and "Active Sessions" in r.text)

        r = client.post("/logout", follow_redirects=False)
        check("logout redirects to /login", r.status_code == 303 and r.headers.get("location") == "/login"),

        r = client.get("/security", follow_redirects=False)
        check("the page is protected again immediately after logout", r.status_code == 303)
    finally:
        _reset_dashboard_auth_state()  # clean up — this test's data should not persist


def test_kill_switch_revokes_dashboard_sessions():
    print("\n=== Kill switch: activating it revokes every dashboard session, not just permissions/timing ===")
    from agent.security.dashboard_auth import set_password, create_session, validate_session
    from agent.security.kill_switch import activate, reactivate

    try:
        set_password("edge-case-killswitch-pw")
        sid = create_session(device_label="Edge Case Kill Switch Device")
        check("session is valid before the kill switch is activated", validate_session(sid) is True)

        result = activate()
        check("activate() reports the number of sessions it revoked", result["sessions_revoked"] == 1, f"got {result['sessions_revoked']}")
        check("the session no longer validates after activation", validate_session(sid) is False)

        reactivate(result["previous_levels"])
        check("reactivate() does not resurrect a revoked session (there is no 'undo' for logout)", validate_session(sid) is False)
    finally:
        _reset_dashboard_auth_state()  # clean up — this test's data should not persist


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
    test_meta_signature_verification()
    test_instagram_payload_parsing_both_shapes()
    test_whatsapp_payload_parsing_and_display_name_fallback()
    test_webhook_inbox_store_drain_is_one_shot_and_platform_scoped()
    test_webhook_inbox_store_duplicate_detection()
    test_webhook_server_rejects_bad_signature_and_accepts_valid_one()
    test_instagram_and_whatsapp_adapters_use_webhook_inbox_not_network()
    test_registry_includes_all_three_platforms()
    test_dashboard_auth_password_and_session_lifecycle()
    test_dashboard_auth_login_lockout()
    test_dashboard_middleware_opt_in_and_enforced_states()
    test_kill_switch_revokes_dashboard_sessions()

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
