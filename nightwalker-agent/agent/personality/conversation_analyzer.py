"""
agent/personality/conversation_analyzer.py

Implements the pipeline from the original spec:
    conversation -> analysis -> important information ->
    communication patterns -> structured profile

Given a chunk of imported conversation messages, asks the model to
classify content into:
- communication_style_updates   (how "me" talks — subset of onboarding trait keys)
- behavioral_pattern_updates    (how "me" acts — subset of onboarding trait keys)
- personal_knowledge            (facts "me" has explicitly shared about themself)
- sensitive_information_flags   (short, neutral category flags — NOT full detail)
- notes                         (anything else worth a human glance, free text)

The model is instructed to only extract things attributable to the
"me" speaker, not the other participant, and to flag sensitive content
rather than reproduce it verbatim — those flags get routed to
sensitive_store.py, never into the main profile.
"""

import json
import re

from agent.brain.model_client import ModelClient, ModelClientError

ANALYSIS_SYSTEM_PROMPT = """You analyze a chunk of a real conversation export to learn about ONE
participant, labeled "me" in the transcript. Everything said by other participants is context only
— never attribute their communication style or facts to "me".

Extract:

1. communication_style_updates — an object with any of these keys you have evidence for (omit keys
   with no evidence, do not guess): close_friends_style, strangers_style, emoji_usage,
   slang_and_abbreviations, language_mixing, punctuation_and_caps, message_length, humor_style.
   Each value should be a short phrase describing the pattern you observed.

2. behavioral_pattern_updates — same idea, any of: response_when_happy, response_when_angry,
   response_when_busy, response_to_serious_topics, messages_ignored, messages_urgent,
   conversation_starters, conversation_enders.

3. personal_knowledge — a list of short factual statements "me" explicitly shared about
   themselves (hobbies, job, preferences, ongoing situations). Only include things actually
   stated, never inferred or guessed.

4. sensitive_information_flags — a list of SHORT, NEUTRAL category flags only (a few words each,
   e.g. "mentioned a health concern", "mentioned financial stress", "mentioned a family conflict").
   Do NOT include the actual sensitive detail, names, or verbatim text — just that this category
   of topic came up, so it can be handled with extra care elsewhere.

5. notes — optional short free text for anything ambiguous or worth a human glance.

If a chunk has no useful signal for a category, use an empty object/list for it. Never fabricate
information not present in the transcript.

Respond with ONLY a single JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "communication_style_updates": {},
  "behavioral_pattern_updates": {},
  "personal_knowledge": [],
  "sensitive_information_flags": [],
  "notes": ""
}
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def format_chunk_for_prompt(messages: list[dict]) -> str:
    """
    messages: list of {"speaker": str, "text": str, "timestamp": str (optional)}
    "speaker" should be "me" for the user's own messages, anything else
    for other participants.
    """
    lines = []
    for msg in messages:
        speaker = msg.get("speaker", "unknown")
        text = msg.get("text", "")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def analyze_chunk(messages: list[dict], model_name: str) -> dict:
    """
    Returns the raw extracted dict for one chunk of conversation.
    Caller is responsible for merging communication_style_updates /
    behavioral_pattern_updates / personal_knowledge into the profile
    (via profile_extractor.merge_into_profile) and routing
    sensitive_information_flags to sensitive_store.py.
    """
    client = ModelClient(model_name)
    chunk_text = format_chunk_for_prompt(messages)

    request_messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": chunk_text},
    ]

    try:
        result = client.chat(request_messages)
    except ModelClientError as e:
        raise RuntimeError(f"Could not analyze conversation chunk: {e}") from e

    cleaned = _strip_json_fences(result["content"])
    try:
        extracted = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model did not return valid JSON for conversation analysis. Raw output:\n{cleaned}"
        ) from e

    # Normalize missing keys so callers don't need defensive checks everywhere.
    extracted.setdefault("communication_style_updates", {})
    extracted.setdefault("behavioral_pattern_updates", {})
    extracted.setdefault("personal_knowledge", [])
    extracted.setdefault("sensitive_information_flags", [])
    extracted.setdefault("notes", "")

    return extracted
