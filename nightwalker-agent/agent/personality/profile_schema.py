"""
agent/personality/profile_schema.py

Defines the structure of the personality profile. Every trait is stored
as {"value": ..., "confidence": float, "evidence_count": int} so later
phases (continuous learning from corrections) can raise or lower
confidence over time instead of overwriting blindly.

Phase 3 additions:
- personal_knowledge: facts the person has explicitly shared (from
  onboarding or imported conversations) — not communication style,
  actual knowledge about them.
- temporary_context: information relevant only briefly. Kept here so
  the shape exists, but nothing writes long-lived data into it yet —
  real expiry handling arrives with the Phase 4 memory architecture.
- style_corrections: raw tally of correction patterns (AI suggestion
  vs. what the person actually sent), keyed by a short tag. One
  correction is a weak signal; repeated corrections of the same
  pattern raise confidence and eventually promote into learned_patterns.
- learned_patterns: plain-language patterns promoted from repeated
  corrections, once they've been seen enough times to trust.

Sensitive information is deliberately NOT part of this schema — it is
stored separately (see sensitive_store.py) because it needs stronger
protection than the rest of the profile. As of Phase 3 that separate
file is still plaintext; encryption at rest is planned for the Phase 8
security architecture and has not been built yet.
"""

import datetime

# Starting confidence for a trait set directly from an onboarding answer.
# Direct statements are more reliable than inferred behavior, but this is
# still just one session — see the continuous-learning principle: one
# signal is weak, repeated signals are strong.
ONBOARDING_CONFIDENCE = 0.5

# Starting confidence for a trait inferred from imported conversation
# history. Slightly lower than a direct onboarding answer because it's
# inferred from context rather than stated outright.
CONVERSATION_IMPORT_CONFIDENCE = 0.35


def _trait(value=None, confidence=0.0, evidence_count=0):
    return {"value": value, "confidence": confidence, "evidence_count": evidence_count}


def empty_profile() -> dict:
    """Returns a fresh, unfilled profile structure."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "meta": {
            "created_at": now,
            "last_updated": now,
            "onboarding_sessions_completed": 0,
        },
        "communication_style": {
            "close_friends_style": _trait(),
            "strangers_style": _trait(),
            "emoji_usage": _trait(),
            "slang_and_abbreviations": _trait(),
            "language_mixing": _trait(),
            "punctuation_and_caps": _trait(),
            "message_length": _trait(),
            "humor_style": _trait(),
        },
        "behavioral_patterns": {
            "response_when_happy": _trait(),
            "response_when_angry": _trait(),
            "response_when_busy": _trait(),
            "response_to_serious_topics": _trait(),
            "messages_ignored": _trait(),
            "messages_urgent": _trait(),
            "conversation_starters": _trait(),
            "conversation_enders": _trait(),
        },
        "personal_knowledge": [],
        "temporary_context": [],
        "style_corrections": {},
        "learned_patterns": [],
        "boundaries": {
            "never_say": [],
            "actions_requiring_approval": [],
            "actions_never_allowed": [],
        },
        "raw_onboarding_transcripts": [],
        "raw_conversation_imports": [],
    }
