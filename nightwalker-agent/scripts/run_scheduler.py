"""
scripts/run_scheduler.py

Runs the background job scheduler (agent/scheduler/scheduler.py) as
its own standalone process — for when you want housekeeping to keep
running without also having the dashboard open. If you DO run the
dashboard, it already auto-starts this same scheduler on its own (see
dashboard/app.py) — running both at once is harmless (see
scheduler.py's "RUNNING WITH MULTIPLE PROCESSES" section), just
mildly redundant.

Usage:
    python scripts/run_scheduler.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.scheduler import scheduler
from agent.scheduler.jobs import register_default_jobs

if __name__ == "__main__":
    register_default_jobs()
    scheduler.start()

    print("NightWalker scheduler running. Registered jobs:")
    for job in scheduler.list_jobs():
        print(f"  - {job['name']} (every {job['interval_seconds']}s)")
    print("\nPress Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping.")
        scheduler.stop()
