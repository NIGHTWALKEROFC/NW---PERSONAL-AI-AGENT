"""
scripts/pause_agent.py

Manual pause control, per spec section 5/20: pause 10 minutes, pause
1 hour, pause indefinitely, or resume. This is the timing engine's
pause — not the full security kill switch (Phase 8), which will also
need to stop schedulers and revoke sessions once those exist.

Usage:
    python scripts/pause_agent.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.timing.pause_control import pause_for, pause_indefinitely, resume, is_paused


def main():
    paused, reason = is_paused()
    if paused:
        print(f"Currently paused: {reason}")
    else:
        print("Currently not paused.")

    print("\n1) Pause 10 minutes")
    print("2) Pause 1 hour")
    print("3) Pause indefinitely (until manually resumed)")
    print("4) Resume now")
    print("5) Just checking — do nothing")

    choice = input("\nChoice: ").strip()

    if choice == "1":
        resume_at = pause_for(10)
        print(f"Paused for 10 minutes. Will resume at {resume_at}.")
    elif choice == "2":
        resume_at = pause_for(60)
        print(f"Paused for 1 hour. Will resume at {resume_at}.")
    elif choice == "3":
        pause_indefinitely()
        print("Paused indefinitely. Run this script again and choose 'Resume' to lift it.")
    elif choice == "4":
        resume()
        print("Resumed.")
    else:
        print("No changes made.")


if __name__ == "__main__":
    main()
