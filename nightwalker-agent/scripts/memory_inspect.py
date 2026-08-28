"""
scripts/memory_inspect.py

Quick terminal view into what's actually stored across the memory
layers — short-term, long-term, temporary, contacts, tasks, and the
personality profile summary. This is a stand-in for the Phase 7
dashboard's memory screen, which doesn't exist yet.

Usage:
    python scripts/memory_inspect.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.memory_store import get_recent_short_term, get_long_term_memory, get_active_temporary_memory
from database.contact_store import list_contacts, get_contact_memories
from database.task_store import list_tasks
from agent.personality.profile_store import load_profile, profile_exists
from agent.personality.sensitive_store import list_entries as list_sensitive_entries


def main():
    print("=== Personality Profile ===")
    if not profile_exists():
        print("  No profile yet — run scripts/run_onboarding.py first.\n")
    else:
        profile = load_profile()
        print(f"  Onboarding sessions completed: {profile['meta']['onboarding_sessions_completed']}")
        print(f"  Last updated: {profile['meta']['last_updated']}")
        filled_traits = sum(
            1 for section in ("communication_style", "behavioral_patterns")
            for t in profile[section].values() if t["value"]
        )
        print(f"  Traits with data: {filled_traits}")
        print(f"  Personal knowledge facts: {len(profile['personal_knowledge'])}")
        print(f"  Learned patterns from corrections: {len(profile['learned_patterns'])}")
        print()

    print("=== Sensitive Info Flags (category only, not encrypted yet) ===")
    sensitive = list_sensitive_entries()
    print(f"  {len(sensitive)} flag(s) recorded")
    for entry in sensitive[:5]:
        print(f"    - {entry['flag']} (from {entry['source']})")
    print()

    print("=== Short-term memory (general, no contact) ===")
    recent = get_recent_short_term(limit=10, contact_id=None)
    print(f"  {len(recent)} of last 10 shown")
    for msg in recent[-5:]:
        print(f"    [{msg['role']}] {msg['content'][:80]}")
    print()

    print("=== Long-term memory ===")
    long_term = get_long_term_memory()
    print(f"  {len(long_term)} entries")
    for entry in long_term[:5]:
        print(f"    - ({entry['category']}, importance {entry['importance']}) {entry['content'][:80]}")
    print()

    print("=== Active temporary memory ===")
    temp = get_active_temporary_memory()
    print(f"  {len(temp)} active entries")
    for entry in temp[:5]:
        print(f"    - {entry['content'][:80]} (expires {entry['expires_at']})")
    print()

    print("=== Contacts ===")
    contacts = list_contacts()
    print(f"  {len(contacts)} contact(s)")
    for c in contacts:
        memories = get_contact_memories(c["id"])
        print(f"    - {c['name']} ({c.get('platform') or 'no platform set'}): {len(memories)} memories")
    print()

    print("=== Tasks ===")
    tasks = list_tasks()
    print(f"  {len(tasks)} task(s)")
    for t in tasks[:5]:
        print(f"    - [{t['status']}] {t['goal']}")


if __name__ == "__main__":
    main()
