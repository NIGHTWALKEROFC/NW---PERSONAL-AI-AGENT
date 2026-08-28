"""
agent/reply/context_builder.py

This is where the personality profile and memory actually start
mattering: instead of agent/core.py's generic static system prompt,
this builds one fresh per message from:

- communication_style / behavioral_patterns traits above a minimum
  confidence (weak, unconfirmed traits are left out rather than
  guessed from)
- learned_patterns promoted from repeated corrections (Phase 3)
- a capped number of personal_knowledge facts (most recent first —
  proper relevance retrieval needs the vector search the spec
  mentions as a later addition; this is a simple recency cap for now)
- boundaries: never_say is given to the model directly as hard
  instructions; actions_requiring_approval / actions_never_allowed are
  included as context so the model doesn't casually offer to do them,
  though there is no permission engine yet to actually enforce this
  (that's Phase 8) — this is advisory, not enforced
- contact-specific context (relationship_context, common topics,
  important memories) if a contact_id is given
- a capped number of the highest-importance long-term memories

Sensitive information is deliberately never pulled in here — it stays
in its own store and is never sent into a prompt by this pipeline.
"""

from agent.personality.profile_store import load_profile
from database.memory_store import get_recent_short_term, get_long_term_memory
from database.contact_store import get_contact_memories, get_contact_by_name

# Traits below this confidence are too weak to state as fact to the model —
# left out rather than guessed from.
MIN_TRAIT_CONFIDENCE = 0.3

MAX_PERSONAL_KNOWLEDGE_FACTS = 15
MAX_LONG_TERM_MEMORIES = 5
MAX_CONTACT_MEMORIES_PER_TYPE = 5

BASE_INSTRUCTION = (
    "You are drafting a message on behalf of a real person, in their own voice. "
    "Do not sound like a generic assistant — no corporate language, no unnecessary "
    "explanations, no excessive politeness, no repetitive phrasing. Keep it natural "
    "and match the style described below as closely as the evidence supports."
)


def _describe_traits(profile: dict) -> str:
    lines = []
    for section in ("communication_style", "behavioral_patterns"):
        for trait_key, trait_data in profile[section].items():
            if trait_data["value"] and trait_data["confidence"] >= MIN_TRAIT_CONFIDENCE:
                readable_key = trait_key.replace("_", " ")
                lines.append(f"- {readable_key}: {trait_data['value']}")
    return "\n".join(lines) if lines else "(No confirmed style traits yet — run onboarding or import conversations.)"


def _describe_learned_patterns(profile: dict) -> str:
    patterns = profile.get("learned_patterns", [])
    if not patterns:
        return ""
    lines = "\n".join(f"- {p}" for p in patterns)
    return f"\nAdditional patterns learned from real corrections:\n{lines}"


def _describe_personal_knowledge(profile: dict) -> str:
    facts = profile.get("personal_knowledge", [])
    if not facts:
        return ""
    recent = facts[-MAX_PERSONAL_KNOWLEDGE_FACTS:]
    lines = "\n".join(f"- {f['fact']}" for f in recent)
    return f"\nThings this person has shared about themselves:\n{lines}"


def _describe_boundaries(profile: dict) -> str:
    b = profile.get("boundaries", {})
    parts = []
    if b.get("never_say"):
        lines = "\n".join(f"- {item}" for item in b["never_say"])
        parts.append(f"\nNEVER say or imply any of the following, under any circumstance:\n{lines}")
    if b.get("actions_never_allowed"):
        lines = "\n".join(f"- {item}" for item in b["actions_never_allowed"])
        parts.append(f"\nNever suggest, offer, or agree to do any of the following:\n{lines}")
    if b.get("actions_requiring_approval"):
        lines = "\n".join(f"- {item}" for item in b["actions_requiring_approval"])
        parts.append(
            f"\nThe following require the real person's explicit approval before happening — "
            f"do not draft a message that implies these have already been done or agreed to:\n{lines}"
        )
    return "".join(parts)


def _describe_long_term_memory() -> str:
    entries = get_long_term_memory()[:MAX_LONG_TERM_MEMORIES]
    if not entries:
        return ""
    lines = "\n".join(f"- ({e['category']}) {e['content']}" for e in entries)
    return f"\nRelevant long-term memory:\n{lines}"


def _describe_contact_context(contact_id: int) -> str:
    contact = None
    memories = get_contact_memories(contact_id)
    if not memories:
        return ""

    grouped: dict[str, list[str]] = {}
    for m in memories:
        grouped.setdefault(m["memory_type"], []).append(m["content"])

    parts = [f"\nContext about this specific conversation partner:"]
    for memory_type, contents in grouped.items():
        label = memory_type.replace("_", " ")
        capped = contents[:MAX_CONTACT_MEMORIES_PER_TYPE]
        lines = "\n".join(f"  - {c}" for c in capped)
        parts.append(f"  {label}:\n{lines}")
    return "\n".join(parts)


def build_system_prompt(contact_id: int | None = None) -> str:
    """Assembles the full dynamic system prompt from everything currently known."""
    profile = load_profile()

    sections = [
        BASE_INSTRUCTION,
        "\nCommunication style (only confirmed patterns shown):",
        _describe_traits(profile),
        _describe_learned_patterns(profile),
        _describe_personal_knowledge(profile),
        _describe_boundaries(profile),
        _describe_long_term_memory(),
    ]

    if contact_id is not None:
        sections.append(_describe_contact_context(contact_id))

    return "\n".join(s for s in sections if s)


def build_context_messages(contact_id: int | None = None, recent_limit: int = 10) -> list[dict]:
    """
    Returns a ready-to-use messages list: [system prompt, ...recent short-term history]
    with roles translated to what the model API expects. Does not include the new
    incoming message — the caller appends that.
    """
    system_prompt = build_system_prompt(contact_id)
    messages = [{"role": "system", "content": system_prompt}]

    recent = get_recent_short_term(limit=recent_limit, contact_id=contact_id)
    for msg in recent:
        role = "user" if msg["role"] == "me" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    return messages


def resolve_contact_id(contact_name: str | None) -> int | None:
    """Looks up an existing contact by name without creating one — this pipeline
    only reads context, it doesn't register new contacts (that happens through
    conversation import or explicit contact management, not reply generation)."""
    if not contact_name:
        return None
    contact = get_contact_by_name(contact_name)
    return contact["id"] if contact else None
