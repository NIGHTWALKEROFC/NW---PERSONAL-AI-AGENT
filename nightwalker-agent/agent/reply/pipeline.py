"""
agent/reply/pipeline.py

Ties together the full reply pipeline, matching the spec's exact flow
(section 4):

    generate candidates -> select most natural -> safety/privacy check
    -> permission check -> timing engine -> send or request approval

Phase 9 fix: the timing engine (Phase 6) existed but was never actually
connected to this pipeline until now — it just sat unused. This closes
that gap, in the order the spec specifies: permission is checked
first, then timing decides whether now is actually a good time to act.

If timing says "not allowed right now" (manually paused, or within
configured sleep hours), that OVERRIDES everything else — even an
AUTO-permitted, quality-passed reply won't proceed, and even an ASK-
level reply does NOT get queued for approval. The reasoning: sleep
hours / an active pause mean "don't act right now," and pinging for
approval during quiet hours defeats that intent.

What this still does NOT do: actually send anything anywhere (no
platform connectors exist — Phase 10), or sleep the process to honor
a timing delay (there's no send loop to schedule against yet). The
delay is reported as information, not enforced.
"""

from agent.brain.model_manager import get_active_model
from agent.personality.profile_store import load_profile
from agent.reply.context_builder import build_context_messages, build_system_prompt, resolve_contact_id
from agent.reply.candidate_generator import generate_candidates
from agent.reply.candidate_selector import select_best_candidate
from agent.reply.quality_check import run_quality_checks
from database.memory_store import get_recent_short_term
from agent.security.permission_engine import get_permission
from agent.security.approval_queue import create_approval
from agent.timing.timing_engine import decide_timing


def generate_reply(incoming_message: str, contact_name: str | None = None) -> dict:
    """
    Runs the full pipeline for one incoming message. Returns:

    {
        "status": "ready" | "pending_approval" | "needs_review" | "blocked" | "timing_blocked",
        "selected_text": str,
        "selected_index": int,
        "selection_reasoning": str,
        "all_candidates": [...],
        "quality": {"passed": bool, "concerns": [...], "self_check": {...}},
        "contact_id": int | None,
        "permission_level": str | None,
        "approval_id": int | None,
        "timing": {...} | None,   # from timing_engine.decide_timing()
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
            "permission_level": None,
            "approval_id": None,
            "timing": None,
        }

    style_summary = build_system_prompt(contact_id=contact_id)
    selection = select_best_candidate(candidates, style_summary, model_name)

    profile = load_profile()
    recent = get_recent_short_term(limit=10, contact_id=contact_id)
    recent_agent_texts = [m["content"] for m in recent if m["role"] == "agent"]

    quality = run_quality_checks(
        selection["selected_text"], profile, recent_agent_texts, model_name
    )

    if not quality["passed"]:
        return {
            "status": "needs_review",
            "selected_text": selection["selected_text"],
            "selected_index": selection["selected_index"],
            "selection_reasoning": selection["reasoning"],
            "all_candidates": selection["all_candidates"],
            "quality": quality,
            "contact_id": contact_id,
            "permission_level": None,
            "approval_id": None,
            "timing": None,
        }

    permission_level = get_permission("send_normal_reply")

    if permission_level in ("DISABLED", "NEVER"):
        return {
            "status": "blocked",
            "selected_text": selection["selected_text"],
            "selected_index": selection["selected_index"],
            "selection_reasoning": selection["reasoning"],
            "all_candidates": selection["all_candidates"],
            "quality": quality,
            "contact_id": contact_id,
            "permission_level": permission_level,
            "approval_id": None,
            "timing": None,
        }

    timing = decide_timing(contact_name)

    if not timing["allowed"]:
        # Sleep hours or manual pause — don't act at all, not even queue an approval.
        return {
            "status": "timing_blocked",
            "selected_text": selection["selected_text"],
            "selected_index": selection["selected_index"],
            "selection_reasoning": selection["reasoning"],
            "all_candidates": selection["all_candidates"],
            "quality": quality,
            "contact_id": contact_id,
            "permission_level": permission_level,
            "approval_id": None,
            "timing": timing,
        }

    approval_id = None
    if permission_level == "ASK":
        approval_id = create_approval(
            action_type="send_normal_reply",
            payload={"draft_text": selection["selected_text"], "incoming_message": incoming_message},
            reasoning=selection["reasoning"],
            contact_id=contact_id,
        )
        status = "pending_approval"
    else:  # AUTO or SUGGEST
        status = "ready"

    return {
        "status": status,
        "selected_text": selection["selected_text"],
        "selected_index": selection["selected_index"],
        "selection_reasoning": selection["reasoning"],
        "all_candidates": selection["all_candidates"],
        "quality": quality,
        "contact_id": contact_id,
        "permission_level": permission_level,
        "approval_id": approval_id,
        "timing": timing,
    }
