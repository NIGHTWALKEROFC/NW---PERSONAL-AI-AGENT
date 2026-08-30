"""
agent/personality/correction_learning.py

Implements the spec's continuous-learning principle:
    original AI suggestion -> person's edited version -> learn the difference
    one correction = weak signal, repeated pattern = strong signal

Every correction is logged in the corrections_log table. As of Phase
8, the original/edited/description text fields are encrypted at rest
(tags stay plaintext JSON — they're short category labels, not
personal content, and keeping them readable is harmless). See
database/crypto.py for what this encryption does and doesn't protect
against.

Phase 5 (reply generation) auto-feeds this via scripts/generate_reply.py.
scripts/log_correction.py lets you feed it manually too.

If you have data from before Phase 8, run
scripts/encrypt_existing_data.py once to encrypt it in place.
"""

import datetime
import json
import re

from agent.brain.model_client import ModelClient, ModelClientError
from agent.personality.profile_store import load_profile, save_profile
from database.db import get_connection
from database.crypto import encrypt_text, decrypt_text

CORRECTION_PROMOTION_THRESHOLD = 3

TAG_EXTRACTION_SYSTEM_PROMPT = """You compare an AI-generated draft message with the version the
person actually sent instead. Identify the stylistic differences as short snake_case tags (a few
words each, e.g. "adds_emoji", "shortens_sentence", "more_casual_tone", "adds_extra_letter_emphasis",
"removes_punctuation", "adds_slang"). Only tag differences that reflect the PERSON'S actual voice,
not random rewording.

Also give one short plain-language description summarizing the overall pattern (one sentence).

Respond with ONLY a JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "tags": ["tag_one", "tag_two"],
  "description": "one sentence describing the pattern"
}
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _log_correction_row(timestamp: str, original: str, edited: str, tags: list[str], description: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO corrections_log (timestamp, original, edited, tags, description) VALUES (?, ?, ?, ?, ?)",
        (timestamp, encrypt_text(original), encrypt_text(edited), json.dumps(tags), encrypt_text(description)),
    )
    conn.commit()


def get_corrections_log() -> list[dict]:
    """Returns the full correction history, most recent first, decrypted."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM corrections_log ORDER BY id DESC").fetchall()
    results = []
    for r in rows:
        entry = dict(r)
        entry["tags"] = json.loads(entry["tags"])
        entry["original"] = decrypt_text(entry["original"])
        entry["edited"] = decrypt_text(entry["edited"])
        entry["description"] = decrypt_text(entry["description"])
        results.append(entry)
    return results


def _extract_pattern_tags(original: str, edited: str, model_name: str) -> dict:
    client = ModelClient(model_name)
    messages = [
        {"role": "system", "content": TAG_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"AI draft: {original}\nPerson actually sent: {edited}"},
    ]
    try:
        result = client.chat(messages)
    except ModelClientError as e:
        raise RuntimeError(f"Could not analyze correction: {e}") from e

    cleaned = _strip_json_fences(result["content"])
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model did not return valid JSON for correction tags. Raw output:\n{cleaned}") from e

    parsed.setdefault("tags", [])
    parsed.setdefault("description", "")
    return parsed


def _tag_confidence(count: int) -> float:
    return round(min(0.9, 0.05 + 0.15 * count), 2)


def log_correction(original: str, edited: str, model_name: str) -> dict:
    now = datetime.datetime.utcnow().isoformat() + "Z"

    tag_result = _extract_pattern_tags(original, edited, model_name)
    tags = tag_result["tags"]
    description = tag_result["description"]

    _log_correction_row(now, original, edited, tags, description)

    profile = load_profile()
    newly_promoted = []

    for tag in tags:
        existing = profile["style_corrections"].get(tag, {
            "count": 0,
            "example_original": original,
            "example_edited": edited,
            "confidence": 0.0,
            "last_seen": now,
            "promoted": False,
        })
        existing["count"] += 1
        existing["confidence"] = _tag_confidence(existing["count"])
        existing["last_seen"] = now
        existing["example_original"] = original
        existing["example_edited"] = edited

        if existing["count"] >= CORRECTION_PROMOTION_THRESHOLD and not existing["promoted"]:
            existing["promoted"] = True
            pattern_note = f"{description} (pattern: {tag}, confidence: {existing['confidence']})"
            if pattern_note not in profile["learned_patterns"]:
                profile["learned_patterns"].append(pattern_note)
            newly_promoted.append(tag)

        profile["style_corrections"][tag] = existing

    profile["meta"]["last_updated"] = now
    save_profile(profile)

    return {
        "tags": tags,
        "description": description,
        "newly_promoted": newly_promoted,
        "tag_confidences": {t: profile["style_corrections"][t]["confidence"] for t in tags},
    }
