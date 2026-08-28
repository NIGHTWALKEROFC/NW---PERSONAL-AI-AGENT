"""
agent/personality/profile_extractor.py

Takes extracted trait data (from onboarding OR from conversation import —
see conversation_analyzer.py) and merges it into the stored profile.

Important: this does NOT overwrite a trait with weaker evidence than it
already has. Confidence only strengthens with repeated, consistent
signals — a single new answer never silently erases prior evidence.

Phase 3 adds:
- a `source` parameter so onboarding answers and conversation-derived
  inferences start at different confidence levels (direct statements
  are more reliable than inferred patterns)
- handling for personal_knowledge as an appendable list of facts
- sensitive_information is explicitly never handled here — see
  sensitive_store.py. If it somehow arrives in `extracted`, it is
  dropped rather than merged, on purpose.
"""

import datetime
import json
import re

from agent.brain.model_client import ModelClient, ModelClientError
from agent.personality.profile_schema import ONBOARDING_CONFIDENCE, CONVERSATION_IMPORT_CONFIDENCE

EXTRACTION_SYSTEM_PROMPT = """You extract structured personality data from an interview transcript.

You will be given question/answer pairs. For EACH of the following trait keys, produce a short
value (a phrase or a couple of sentences, in the person's own implied style — do not invent
information not supported by their answers):

close_friends_style, strangers_style, emoji_usage, slang_and_abbreviations, language_mixing,
punctuation_and_caps, message_length, humor_style, response_when_happy, response_when_angry,
response_when_busy, response_to_serious_topics, messages_ignored, messages_urgent,
conversation_starters, conversation_enders

Also extract these as LISTS of short strings (one item per distinct thing mentioned):
never_say, actions_requiring_approval, actions_never_allowed

If the transcript gives no information for a trait, use null for that trait's value (for the
list fields, use an empty list instead of null).

Respond with ONLY a single JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "close_friends_style": "...",
  "strangers_style": "...",
  "emoji_usage": "...",
  "slang_and_abbreviations": "...",
  "language_mixing": "...",
  "punctuation_and_caps": "...",
  "message_length": "...",
  "humor_style": "...",
  "response_when_happy": "...",
  "response_when_angry": "...",
  "response_when_busy": "...",
  "response_to_serious_topics": "...",
  "messages_ignored": "...",
  "messages_urgent": "...",
  "conversation_starters": "...",
  "conversation_enders": "...",
  "never_say": ["..."],
  "actions_requiring_approval": ["..."],
  "actions_never_allowed": ["..."]
}
"""

# Keys that live under profile["communication_style"]
_COMMUNICATION_KEYS = {
    "close_friends_style", "strangers_style", "emoji_usage",
    "slang_and_abbreviations", "language_mixing", "punctuation_and_caps",
    "message_length", "humor_style",
}

# Keys that live under profile["behavioral_patterns"]
_BEHAVIORAL_KEYS = {
    "response_when_happy", "response_when_angry", "response_when_busy",
    "response_to_serious_topics", "messages_ignored", "messages_urgent",
    "conversation_starters", "conversation_enders",
}

_BOUNDARY_LIST_KEYS = {"never_say", "actions_requiring_approval", "actions_never_allowed"}


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def extract_traits(transcript: list[dict], model_name: str) -> dict:
    """
    Used by the onboarding flow. transcript: list of
    {"topic": str, "question": str, "answer": str, "follow_up": str|None, "follow_up_answer": str|None}
    Returns the raw extracted dict (before merging into the stored profile).
    """
    client = ModelClient(model_name)

    transcript_text_lines = []
    for turn in transcript:
        transcript_text_lines.append(f"Q: {turn['question']}\nA: {turn['answer']}")
        if turn.get("follow_up"):
            transcript_text_lines.append(f"Follow-up Q: {turn['follow_up']}\nFollow-up A: {turn.get('follow_up_answer', '')}")
    transcript_text = "\n\n".join(transcript_text_lines)

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": transcript_text},
    ]

    try:
        result = client.chat(messages)
    except ModelClientError as e:
        raise RuntimeError(f"Could not extract personality traits: {e}") from e

    cleaned = _strip_json_fences(result["content"])
    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model did not return valid JSON for trait extraction. Raw output:\n{cleaned}"
        ) from e

    return extracted


def merge_into_profile(profile: dict, extracted: dict, source: str = "onboarding") -> dict:
    """
    Merges extracted traits into an existing profile dict, respecting
    confidence — never lowers it, and only strengthens it with each
    new piece of consistent evidence.

    source: "onboarding" or "conversation_import" — determines the
    starting confidence level for brand-new traits.
    """
    base_confidence = ONBOARDING_CONFIDENCE if source == "onboarding" else CONVERSATION_IMPORT_CONFIDENCE
    now = datetime.datetime.utcnow().isoformat() + "Z"

    for key, value in extracted.items():
        if key == "sensitive_information":
            # Sensitive data is never merged here — see sensitive_store.py.
            # If a caller accidentally passes it in, drop it rather than store it.
            continue

        if key == "personal_knowledge":
            if not isinstance(value, list):
                continue
            existing = profile.setdefault("personal_knowledge", [])
            existing_facts = {e["fact"] for e in existing}
            for fact in value:
                if fact and fact not in existing_facts:
                    existing.append({"fact": fact, "added_at": now, "source": source})
                    existing_facts.add(fact)
            continue

        if key in _COMMUNICATION_KEYS:
            section = profile["communication_style"]
        elif key in _BEHAVIORAL_KEYS:
            section = profile["behavioral_patterns"]
        elif key in _BOUNDARY_LIST_KEYS:
            existing = profile["boundaries"].get(key, [])
            if isinstance(value, list):
                combined = existing + [v for v in value if v not in existing]
                profile["boundaries"][key] = combined
            continue
        else:
            continue  # unknown key from model output — ignore rather than crash

        if value is None:
            continue

        existing_trait = section.get(key, {"value": None, "confidence": 0.0, "evidence_count": 0})
        new_evidence_count = existing_trait["evidence_count"] + 1
        new_confidence = min(
            0.95,
            max(existing_trait["confidence"], base_confidence) + 0.05 * (new_evidence_count - 1),
        )

        section[key] = {
            "value": value,
            "confidence": round(new_confidence, 2),
            "evidence_count": new_evidence_count,
        }

    return profile
