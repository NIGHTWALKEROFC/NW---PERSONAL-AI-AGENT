"""
agent/reply/candidate_selector.py

Implements the spec's "select the most natural candidate" step. Shows
the model all generated candidates plus a summary of the confirmed
style traits, and asks it to pick which one best matches — with a
short reason, so the choice is inspectable rather than a black box.

If only one candidate survived generation (the others failed), this
skips the selection call entirely and just returns that one — no need
to "choose" between one option.
"""

import json
import re

from agent.brain.model_client import ModelClient, ModelClientError

SELECTION_SYSTEM_PROMPT = """You are given several candidate draft messages, all written for the
same person, and a short description of that person's confirmed communication style. Pick the
ONE candidate that best matches their real style — most natural, least generic-sounding, best fit
for the traits described. Do not pick based on which is "nicest" or most polished — pick the one
that sounds most like an authentic message from this specific person.

Respond with ONLY a JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "chosen_index": 0,
  "reasoning": "one short sentence explaining the choice"
}

chosen_index is zero-based, referring to the order the candidates were listed in.
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def select_best_candidate(candidates: list[dict], style_summary: str, model_name: str) -> dict:
    """
    candidates: list of {"text": str, "temperature": float} from candidate_generator
    style_summary: a short plain-text description of the confirmed style
    (the caller typically passes the same traits section used in the system prompt)

    Returns {"selected_text": str, "selected_index": int, "reasoning": str, "all_candidates": [...]}
    """
    if not candidates:
        raise ValueError("No candidates were generated — nothing to select from.")

    if len(candidates) == 1:
        return {
            "selected_text": candidates[0]["text"],
            "selected_index": 0,
            "reasoning": "Only one candidate was generated successfully.",
            "all_candidates": candidates,
        }

    candidate_list_text = "\n".join(f"[{i}] {c['text']}" for i, c in enumerate(candidates))

    client = ModelClient(model_name)
    messages = [
        {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Confirmed style:\n{style_summary}\n\nCandidates:\n{candidate_list_text}",
        },
    ]

    try:
        result = client.chat(messages)
    except ModelClientError as e:
        # Fall back to the middle-temperature candidate rather than failing outright —
        # a reasonable default when the selection call itself has trouble.
        fallback_index = len(candidates) // 2
        return {
            "selected_text": candidates[fallback_index]["text"],
            "selected_index": fallback_index,
            "reasoning": f"Selection call failed ({e}); used a default middle candidate instead.",
            "all_candidates": candidates,
        }

    cleaned = _strip_json_fences(result["content"])
    try:
        parsed = json.loads(cleaned)
        chosen_index = int(parsed["chosen_index"])
        reasoning = parsed.get("reasoning", "")
        if not (0 <= chosen_index < len(candidates)):
            raise ValueError("chosen_index out of range")
    except (json.JSONDecodeError, KeyError, ValueError):
        # Model didn't return usable JSON — fall back rather than crash the pipeline.
        chosen_index = len(candidates) // 2
        reasoning = "Could not parse selection response; used a default middle candidate instead."

    return {
        "selected_text": candidates[chosen_index]["text"],
        "selected_index": chosen_index,
        "reasoning": reasoning,
        "all_candidates": candidates,
    }
