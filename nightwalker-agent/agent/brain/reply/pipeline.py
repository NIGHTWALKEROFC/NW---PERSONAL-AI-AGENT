"""
agent/reply/pipeline.py

Ties together the full Phase 5 pipeline, matching the spec's flow:

    incoming message
    -> retrieve context/memory
    -> generate multiple internal candidates
    -> select the most natural candidate
    -> safety/privacy + quality self-check
    -> return result (status: "ready" or "needs_review")

What this does NOT do (by design, later phases):
- does not check any real permission engine (Phase 8 doesn't exist)
- does not apply timing/delay logic (Phase 6 doesn't exist)
- does not send anything anywhere (no platform connectors exist —
  Phase 10) — this only ever returns text for a human to look at
- does not automatically persist the generated reply to short-term
  memory — this is exploratory/preview generation ("what would the
  agent say"), not an actual conversation turn. If you decide to
  actually use a generated reply, log it as a correction (if you'd
  change it) via agent.personality.correction_learning.log_correction,
  which is what scripts/generate_reply.py does for you interactively.
"""

from agent.brain.model_manager import get_active_model
from agent.personality.profile_store import load_profile
from agent.reply.context_builder import build_context_messages, build_system_prompt, resolve_contact_id
from agent.reply.candidate_generator import generate_candidates
from agent.reply.candidate_selector import select_best_candidate
from agent.reply.quality_check import run_quality_checks
from database.memory_store import get_recent_short_term


def generate_reply(incoming_message: str, contact_name: str | None = None) -> dict:
    """
    Runs the full pipeline for one incoming message. Returns a dict with
    everything needed to inspect what happened, not just the final text:

    {
        "status": "ready" | "needs_review",
        "selected_text": str,
        "selected_index": int,
        "selection_reasoning": str,
        "all_candidates": [...],
        "quality": {"passed": bool, "concerns": [...], "self_check": {...}},
        "contact_id": int | None,
    }
    """
    model_name = get_active_model()
    contact_id = resolve_contact_id(contact_name)

    context_messages = build_context_messages(contact_id=contact_id)
    candidates = generate_candidates(context_messages, incoming_message, model_name)

    if not candidates:
        return {
            "status": "needs_review",
            "selected_text": "",
            "selected_index": -1,
            "selection_reasoning": "No candidates could be generated — check that Ollama is running.",
            "all_candidates": [],
            "quality": {"passed": False, "concerns": ["No candidates generated."], "self_check": {}},
            "contact_id": contact_id,
        }

    # Reuse the same style summary the system prompt was built from, for the selector.
    style_summary = build_system_prompt(contact_id=contact_id)
    selection = select_best_candidate(candidates, style_summary, model_name)

    profile = load_profile()
    recent = get_recent_short_term(limit=10, contact_id=contact_id)
    recent_agent_texts = [m["content"] for m in recent if m["role"] == "agent"]

    quality = run_quality_checks(
        selection["selected_text"], profile, recent_agent_texts, model_name
    )

    status = "ready" if quality["passed"] else "needs_review"

    return {
        "status": status,
        "selected_text": selection["selected_text"],
        "selected_index": selection["selected_index"],
        "selection_reasoning": selection["reasoning"],
        "all_candidates": selection["all_candidates"],
        "quality": quality,
        "contact_id": contact_id,
    }
