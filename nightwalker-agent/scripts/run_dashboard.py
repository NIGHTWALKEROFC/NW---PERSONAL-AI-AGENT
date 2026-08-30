"""
scripts/run_dashboard.py

Launches the local control dashboard. Binds to 127.0.0.1 (localhost)
only by default — per spec section 18, this should be reachable only
from your own laptop unless you explicitly choose otherwise.

If you genuinely want it reachable from other devices on your home
network, change host="127.0.0.1" to host="0.0.0.0" below — but
understand that means anyone else on your network could reach it too,
with zero authentication in front of it (there's no login system —
Phase 8 territory). Not recommended unless you know what you're doing.

Usage:
    python scripts/run_dashboard.py

Then open http://127.0.0.1:8420 in your browser.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn

if __name__ == "__main__":
    print("Starting NightWalker dashboard at http://127.0.0.1:8420")
    print("(Press Ctrl+C to stop)")
    uvicorn.run("dashboard.app:app", host="127.0.0.1", port=8420, reload=False)
