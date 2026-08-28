"""
scripts/import_conversations.py

Import a local conversation export file (see
config/conversation_import_template.json for the expected format) and
learn communication style, behavioral patterns, and personal knowledge
from it.

Usage:
    python scripts/import_conversations.py path/to/your_export.json

This only reads a file already on your disk. Getting your own chat
history out of whatever platform you used and into the expected JSON
format is up to you — this script does not scrape or connect to any
platform.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
from agent.personality.conversation_importer import run_import


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_conversations.py path/to/your_export.json")
        return

    path = sys.argv[1]

    model_name = get_active_model()
    client = ModelClient(model_name)
    if not client.is_available():
        print(
            "\n[!] Cannot reach Ollama. Make sure it's running, then try again.\n"
            "    Check with: ollama list\n"
        )
        return

    try:
        summary = run_import(path)
    except (FileNotFoundError, ValueError) as e:
        print(f"[!] {e}")
        return

    print("\nImport complete.")
    print(f"  Messages processed: {summary['message_count']}")
    print(f"  Chunks analyzed: {summary['chunks_processed']}")
    if summary["chunks_with_errors"]:
        print(f"  Chunks skipped due to errors: {summary['chunks_with_errors']}")
    print(f"  New personal knowledge facts found: {summary['personal_knowledge_facts_found']}")
    if summary["sensitive_flags_found"]:
        print(
            f"  Sensitive topic flags recorded: {summary['sensitive_flags_found']} "
            "(stored separately in database/sensitive_profile.json — see that file's "
            "docstring for its current, unencrypted, security status)"
        )


if __name__ == "__main__":
    main()
