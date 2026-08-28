"""
agent/reply/quality_check.py

Implements the spec's reply-quality self-check list:
    does this sound like me? too formal? too long? repeats previous
    wording? reveals anything private? am I actually expected to reply?

This is a QUALITY/SAFETY GATE, not a permission system — there is no
Phase 8 permission engine yet, and no platform connector exists to
actually send anything anywhere. Nothing here auto-sends. The output
is always shown to the person; this only decides whether to label a
draft "ready" or "needs_review" so low-confidence or boundary-crossing
drafts get flagged rather than presented as if they were fine.

Checks run in two layers:
1. Deterministic checks (never_say keyword match, repetition against
   recent history) — these don't depend on the model being right about
   itself, so they run first and are treated as hard fails.
2. A model self-check pass for the softer, more subjective questions
   (does this sound natural, too formal, too long).
"""

import difflib
import json
import re

from agent.brain.model_client import ModelClient, ModelClientError

# A candidate too similar to something already said recently gets flagged —
# not blocked outright (repeating yourself sometimes is normal), just noted.
REPETITION_SIMILARITY_THRESHOLD = 0.85

SELF_CHECK_SYSTEM_PROMPT = """Evaluate ONE draft message against the confirmed communication style
description you're given. Answer honestly and briefly.

Respond with ONLY a JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "sounds_natural": true,
  "too_formal": false,
  "too_long": false,
  "concerns": []
}

"concerns" is a list of short strings for anything else worth flagging (empty list if none).
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _check_never_say(candidate_text: str, never_say_list: list[str]) -> list[str]:
    violations = []
    lowered = candidate_text.lower()
    for phrase in never_say_list:
        if phrase.lower() in lowered:
            violations.append(f"Contains a never-say phrase: \"{phrase}\"")
    return violations


def _check_repetition(candidate_text: str, recent_texts: list[str]) -> list[str]:
    concerns = []
    for prior in recent_texts:
        ratio = difflib.SequenceMatcher(None, candidate_text.lower(), prior.lower()).ratio()
        if ratio >= REPETITION_SIMILARITY_THRESHOLD:
            concerns.append(f"Very similar to a recent message (similarity {ratio:.2f})")
            break  # one flag is enough, no need to list every near-duplicate
    return concerns


def _model_self_check(candidate_text: str, style_summary: str, model_name: str) -> dict:
    client = ModelClient(model_name)
    messages = [
        {"role": "system", "content": SELF_CHECK_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Confirmed style:\n{style_summary}\n\nDraft message:\n{candidate_text}",
        },
    ]
    try:
        result = client.chat(messages)
    except ModelClientError as e:
        return {"sounds_natural": True, "too_formal": False, "too_long": False, "concerns": [f"self-check call failed: {e}"]}

    cleaned = _strip_json_fences(result["content"])
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"sounds_natural": True, "too_formal": False, "too_long": False, "concerns": ["self-check response was not valid JSON"]}

    parsed.setdefault("sounds_natural", True)
    parsed.setdefault("too_formal", False)
    parsed.setdefault("too_long", False)
    parsed.setdefault("concerns", [])
    return parsed


def run_quality_checks(
    candidate_text: str,
    profile: dict,
    recent_texts: list[str],
    model_name: str,
) -> dict:
    """
    Returns {"passed": bool, "concerns": list[str], "self_check": dict}

    "passed" is False if:
    - a never_say phrase is present (hard fail, deterministic)
    - the model self-check reports sounds_natural=False, too_formal=True,
      too_long=True, or any concerns
    Repetition is flagged in "concerns" but does NOT by itself fail the
    check — repeating yourself sometimes is normal human behavior.
    """
    never_say_list = profile.get("boundaries", {}).get("never_say", [])
    hard_violations = _check_never_say(candidate_text, never_say_list)
    repetition_concerns = _check_repetition(candidate_text, recent_texts)

    style_summary_lines = []
    for section in ("communication_style", "behavioral_patterns"):
        for key, data in profile[section].items():
            if data["value"]:
                style_summary_lines.append(f"{key}: {data['value']}")
    style_summary = "\n".join(style_summary_lines) if style_summary_lines else "(no confirmed traits yet)"

    self_check = _model_self_check(candidate_text, style_summary, model_name)

    soft_concerns = []
    if not self_check.get("sounds_natural", True):
        soft_concerns.append("Self-check: does not sound natural.")
    if self_check.get("too_formal"):
        soft_concerns.append("Self-check: too formal.")
    if self_check.get("too_long"):
        soft_concerns.append("Self-check: too long.")
    soft_concerns.extend(self_check.get("concerns", []))

    all_concerns = hard_violations + repetition_concerns + soft_concerns
    passed = len(hard_violations) == 0 and len(soft_concerns) == 0

    return {
        "passed": passed,
        "concerns": all_concerns,
        "self_check": self_check,
    }
