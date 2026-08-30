"""
scripts/timing_check.py

Simulate the timing decision right now, without needing a real
incoming message or platform connection. Useful for testing the engine
and for understanding why it decided what it decided.

Usage:
    python scripts/timing_check.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.timing.timing_engine import decide_timing
from agent.timing.timing_rules import get_time_bucket


def main():
    contact_name = input("Contact name (press enter for general/no contact): ").strip() or None

    bucket = get_time_bucket()
    print(f"\nCurrent time bucket: {bucket}")

    result = decide_timing(contact_name)

    print(f"\nAllowed to act: {result['allowed']}")
    if result["allowed"]:
        print(f"Suggested delay: {result['delay_seconds']} seconds")
        print(f"Based on: {result['based_on']}")
        if result["sample_count"]:
            print(f"Real historical samples used: {result['sample_count']}")
    print(f"Reason: {result['reason']}")


if __name__ == "__main__":
    main()
