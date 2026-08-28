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
"""

import datetime
import json
import os

from agent.brain.model_manager import get_active_model
from agent.personality.conversation_analyzer import analyze_chunk
from agent.personality.profile_extractor import merge_into_profile
from agent.personality.profile_store import load_profile, save_profile
from agent.personality.sensitive_store import append_entries as append_sensitive_entries

CHUNK_SIZE = 30  # messages per analysis call — keeps prompts small and fast


def load_conversation_file(path: str) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No file found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Conversation file must be a JSON array of message objects.")
    return data


def chunk_messages(messages: list[dict], chunk_size: int = CHUNK_SIZE) -> list[list[dict]]:
    return [messages[i:i + chunk_size] for i in range(0, len(messages), chunk_size)]


def run_import(path: str, progress_fn=print) -> dict:
    """
    Runs the full import pipeline for one file. Returns a summary dict.
    progress_fn is called with short status strings as it works through
    chunks, so a CLI (or later, the dashboard) can show progress.
    """
    model_name = get_active_model()
    messages = load_conversation_file(path)
    chunks = chunk_messages(messages)

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
    })
    save_profile(profile)

    return {
        "message_count": len(messages),
        "chunks_processed": len(chunks) - chunks_with_errors,
        "chunks_with_errors": chunks_with_errors,
        "personal_knowledge_facts_found": total_personal_knowledge,
        "sensitive_flags_found": total_sensitive_flags,
    }
