"""
automation/desktop/workflow_builder.py

Converts recorder.py's raw captured events into DesktopAction-shaped
step dicts (see automation/desktop/actions.py), plus the review/edit/
redact functions scripts/teach_me_cli.py uses on each step before
anything gets saved to database/workflow_store.py.

This entire file is pure logic with no GUI/display dependency, so
unlike recorder.py's actual listeners, everything here IS directly
tested using synthetic event data standing in for a real recording.

Conversion rules (build_steps_from_events):
    click event       -> {"action_type": "click",
                           "params": {"x": ..., "y": ...},
                           "expected_state_description": ""}
    key event         -> {"action_type": "type_text",
                           "params": {"text": "<the typed run>"},
                           "expected_state_description": ""}
    key_special event -> {"action_type": "type_text",
                           "params": {"text": "<bracketed marker, e.g. [ENTER]>"},
                           "expected_state_description": ""}

expected_state_description is deliberately left blank by this
conversion step — a raw recording has no idea what the screen looked
like right before each action, and per automation/desktop/
safety_executor.py, 'click' and 'type_text' steps refuse to run with a
blank expected_state_description. That's intentional friction:
build_steps_from_events() alone never produces an immediately-runnable
workflow. Filling these in is exactly what the mandatory review pass
(review_steps() in scripts/teach_me_cli.py, using apply_review_edits()
below) is for; validate_steps() will keep flagging a step as invalid
until it's done.

key_special events (non-printable keys like Enter, Tab, arrows) are
converted into a type_text step carrying a bracketed marker rather
than silently dropped — silently dropping a step the user actually
performed would make replay diverge from the demonstration with no
indication why. Note this marker is inserted literally as typed text
by controller.type_text() on replay (via pyautogui.write) — it is NOT
currently translated back into an actual Enter/Tab keypress. That
translation doesn't exist yet; flagging it here so it isn't assumed to
work by a later phase or by you, testing this on your machine.
"""

from automation.desktop.actions import DesktopAction

_SPECIAL_KEY_MARKERS = {
    "Key.enter": "[ENTER]",
    "Key.tab": "[TAB]",
    "Key.space": " ",
    "Key.backspace": "[BACKSPACE]",
    "Key.esc": "[ESC]",
}


def _special_key_marker(name: str) -> str:
    return _SPECIAL_KEY_MARKERS.get(name, f"[{name.upper()}]")


def build_steps_from_events(events: list[dict]) -> list[dict]:
    """
    Raw recorder events -> unreviewed step dicts. This is an
    intermediate representation, NOT yet validated or safe to save —
    always pass the result through review (apply_review_edits, then
    validate_steps) before persisting via database/workflow_store.py.
    """
    steps = []
    for event in events:
        event_type = event.get("type")
        if event_type == "click":
            steps.append({
                "action_type": "click",
                "params": {"x": event["x"], "y": event["y"]},
                "expected_state_description": "",
                "label": f"Click at ({event['x']}, {event['y']})",
            })
        elif event_type == "key":
            steps.append({
                "action_type": "type_text",
                "params": {"text": event["text"]},
                "expected_state_description": "",
                "label": f"Type: {event['text']!r}",
            })
        elif event_type == "key_special":
            marker = _special_key_marker(event["name"])
            steps.append({
                "action_type": "type_text",
                "params": {"text": marker},
                "expected_state_description": "",
                "label": f"Press {event['name']}",
            })
        else:
            raise ValueError(f"Unknown recorded event type: {event_type!r}")
    return steps


def redact_step_text(step: dict, replacement: str = "[REDACTED]") -> dict:
    """
    Returns a NEW step dict with any typed text replaced. Used when the
    user reviewing a recording flags a step as containing something
    sensitive (a password typed during the demo, etc.) — the original
    text is discarded entirely, not just hidden, since the goal is to
    never persist it in the first place.
    """
    step = dict(step)
    step["params"] = dict(step["params"])
    if step["action_type"] == "type_text":
        step["params"]["text"] = replacement
        step["label"] = f"Type: {replacement} (redacted)"
    return step


def apply_review_edits(
    step: dict,
    *,
    text: str | None = None,
    expected_state_description: str | None = None,
    redact: bool = False,
) -> dict:
    """
    Applies one round of human review to a single step, returning a NEW
    step dict (the input is never mutated). This is the function
    scripts/teach_me_cli.py calls once per captured step during the
    mandatory review pass.

    redact=True takes priority over `text` and discards the original
    typed text entirely, via redact_step_text().
    """
    step = dict(step)
    step["params"] = dict(step["params"])

    if redact and step["action_type"] == "type_text":
        step = redact_step_text(step)
    elif text is not None and step["action_type"] == "type_text":
        step["params"]["text"] = text
        step["label"] = f"Type: {text!r}"

    if expected_state_description is not None:
        step["expected_state_description"] = expected_state_description

    return step


def validate_steps(steps: list[dict]) -> list[str]:
    """
    Returns a list of human-readable problems. An empty list means the
    workflow is structurally valid and safe to save/run.

    Reuses DesktopAction's own validation (valid action_type, the
    expected_state_description requirement for click/type_text) rather
    than re-implementing those rules — a step DesktopAction would
    reject on its own is invalid here too, for the same reason.
    """
    problems = []
    if not steps:
        problems.append("Workflow has no steps.")
    for i, step in enumerate(steps):
        try:
            DesktopAction(
                action_type=step["action_type"],
                params=step.get("params", {}),
                expected_state_description=step.get("expected_state_description", ""),
            )
        except (ValueError, KeyError) as e:
            problems.append(f"Step {i + 1}: {e}")
    return problems
