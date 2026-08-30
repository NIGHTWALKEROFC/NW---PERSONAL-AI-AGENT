"""
agent/personality/conversation_importer.py

Loads a local conversation export file and runs it through the
analysis pipeline in chunks (so a long export doesn't blow past the
model's context window). Results get merged into the personality
profile at conversation_import confidence (lower than direct
onboarding answers — see profile_schema.CONVERSATION_IMPORT_CONFIDENCE).

Expected input file format (a plain JSON array):

[
  {"speaker": "me", "text": "hey what time works tmrw", "timestamp": "2026-01-04T10:22:00Z"},
  {"speaker": "arjun", "text": "maybe 6pm?", "timestamp": "2026-01-04T10:23:00Z"},
  {"speaker": "me", "text": "yeah works for me 👍", "timestamp": "2026-01-04T10:23:30Z"}
]

"speaker" must be exactly "me" for your own messages — anything else
is treated as another participant and used only as context, never
attributed to you. "timestamp" is optional. See
config/conversation_import_template.json for a ready-to-copy template.

This only reads a file already sitting on your own disk — it does not
fetch, scrape, or connect to any platform. Getting your own export out
of WhatsApp/Instagram/Telegram/etc into this format is up to you; this
importer does not automate that step.

Phase 6 addition: besides extracting personality patterns, this now
also persists the raw messages (with their real timestamps) into
conversation_messages, tagged memory_layer='imported_history' and
linked to a single resolved contact. This is what gives the Phase 6
timing engine real historical reply-delay data to learn from, instead
of only ever falling back to config defaults.

Current limitation, stated plainly: this assumes each import file is
one 1:1 conversation with a single other person. If a file contains
messages from multiple other participants (a group chat), they are all
still linked to whichever non-"me" name appears most often — a real
simplification, not a full multi-participant model. That would need
proper group-chat handling, which hasn't been built.
"""

import datetime
import os
from collections import Counter

from agent.brain.model_manager import get_active_model
from agent.personality.conversation_analyzer import analyze_chunk
from agent.personality.profile_extractor import merge_into_profile
from agent.personality.profile_store import load_profile, save_profile
from agent.personality.sensitive_store import append_entries as append_sensitive_entries
from database.contact_store import get_or_create_contact
from database.memory_store import log_message

CHUNK_SIZE = 30  # messages per analysis call — keeps prompts small and fast


def load_conversation_file(path: str) -> list[dict]:
    import json
    if not os.path.exists(path):
        raise FileNotFoundError(f"No file found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Conversation file must be a JSON array of message objects.")
    return data


def chunk_messages(messages: list[dict], chunk_size: int = CHUNK_SIZE) -> list[list[dict]]:
    return [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]


def _resolve_primary_contact_name(messages: list[dict]) -> str | None:
    """Finds the most common non-'me' speaker in the file — see the
    1:1 conversation assumption documented at the top of this file."""
    others = [m.get("speaker") for m in messages if m.get("speaker") and m.get("speaker") != "me"]
    if not others:
        return None
    return Counter(others).most_common(1)[0][0]


def _persist_raw_messages(messages: list[dict], contact_id: int | None) -> int:
    """Persists every message as real history rows for the timing engine to learn from later."""
    count = 0
    for m in messages:
        speaker = m.get("speaker", "unknown")
        text = m.get("text", "")
        timestamp = m.get("timestamp")  # may be None — log_message falls back to "now" if so
        if not text:
            continue
        log_message(
            role=speaker,
            content=text,
            contact_id=contact_id,
            memory_layer="imported_history",
            created_at=timestamp,
        )
        count += 1
    return count


def run_import(path: str, progress_fn=print) -> dict:
    """
    Runs the full import pipeline for one file. Returns a summary dict.
    progress_fn is called with short status strings as it works through
    chunks, so a CLI (or later, the dashboard) can show progress.
    """
    model_name = get_active_model()
    messages = load_conversation_file(path)
    chunks = chunk_messages(messages)

    contact_name = _resolve_primary_contact_name(messages)
    contact_id = get_or_create_contact(contact_name, platform="imported") if contact_name else None
    if contact_name:
        progress_fn(f"Linking this import to contact: {contact_name}")

    persisted_count = _persist_raw_messages(messages, contact_id)
    progress_fn(f"Persisted {persisted_count} raw messages for timing/history analysis.")

    profile = load_profile()
    total_personal_knowledge = 0
    total_sensitive_flags = 0
    chunks_with_errors = 0

    for i, chunk in enumerate(chunks, start=1):
        progress_fn(f"Analyzing chunk {i}/{len(chunks)} ({len(chunk)} messages)...")
        try:
            extracted = analyze_chunk(chunk, model_name)
        except RuntimeError as e:
            progress_fn(f"  [!] Skipped chunk {i} due to an error: {e}")
            chunks_with_errors += 1
            continue

        merge_payload = dict(extracted.get("communication_style_updates", {}))
        merge_payload.update(extracted.get("behavioral_pattern_updates", {}))
        if extracted.get("personal_knowledge"):
            merge_payload["personal_knowledge"] = extracted["personal_knowledge"]
            total_personal_knowledge += len(extracted["personal_knowledge"])

        if merge_payload:
            profile = merge_into_profile(profile, merge_payload, source="conversation_import")

        if extracted.get("sensitive_information_flags"):
            append_sensitive_entries(
                extracted["sensitive_information_flags"],
                source_label=f"conversation_import:{os.path.basename(path)}",
            )
            total_sensitive_flags += len(extracted["sensitive_information_flags"])

    profile["meta"]["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    profile["raw_conversation_imports"].append({
        "file": os.path.basename(path),
        "imported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "message_count": len(messages),
        "chunks_processed": len(chunks) - chunks_with_errors,
        "chunks_with_errors": chunks_with_errors,
        "linked_contact": contact_name,
    })
    save_profile(profile)

    return {
        "message_count": len(messages),
        "chunks_processed": len(chunks) - chunks_with_errors,
        "chunks_with_errors": chunks_with_errors,
        "personal_knowledge_facts_found": total_personal_knowledge,
        "sensitive_flags_found": total_sensitive_flags,
        "linked_contact": contact_name,
        "messages_persisted_for_history": persisted_count,
    }
