"""
scripts/run_onboarding.py

Run this to go through the personality onboarding interview.
Safe to run more than once — later runs reinforce existing traits
rather than overwriting them (see profile_extractor.merge_into_profile).

Usage:
    python scripts/run_onboarding.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model
from agent.personality.onboarding import run_onboarding_interview
from agent.personality.profile_extractor import extract_traits, merge_into_profile
from agent.personality.profile_store import load_profile, save_profile
import datetime


def main():
    model_name = get_active_model()
    client = ModelClient(model_name)

    if not client.is_available():
        print(
            "\n[!] Cannot reach Ollama. Make sure it's running, then try again.\n"
            "    Check with: ollama list\n"
        )
        return

    transcript = run_onboarding_interview()

    if not transcript:
        print("No answers were recorded, so there's nothing to save.")
        return

    print("Extracting your personality profile from the interview...\n")
    try:
        extracted = extract_traits(transcript, model_name)
    except RuntimeError as e:
        print(f"[!] {e}")
        print("Your raw answers were not lost — but structured extraction failed this time.")
        return

    profile = load_profile()
    profile = merge_into_profile(profile, extracted)
    profile["meta"]["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    profile["meta"]["onboarding_sessions_completed"] += 1
    profile["raw_onboarding_transcripts"].append(transcript)

    save_profile(profile)

    print("Saved. Here's what was captured:\n")
    for section_name in ("communication_style", "behavioral_patterns"):
        print(f"--- {section_name} ---")
        for trait_key, trait_data in profile[section_name].items():
            if trait_data["value"]:
                print(f"  {trait_key}: {trait_data['value']}  (confidence: {trait_data['confidence']})")
        print()

    print("--- boundaries ---")
    for key in ("never_say", "actions_requiring_approval", "actions_never_allowed"):
        items = profile["boundaries"].get(key, [])
        if items:
            print(f"  {key}: {items}")


if __name__ == "__main__":
    main()
