"""
scripts/run_dashboard.py

Launches the local control dashboard. Binds to 127.0.0.1 (localhost)
only by default — this should be reachable only from your own laptop
unless you explicitly configure otherwise.

*** MULTI-DEVICE ACCESS (Phase 14) — READ BEFORE CHANGING THE HOST ***
To reach the dashboard from another device (phone, tablet), set these
in .env:
    DASHBOARD_HOST=0.0.0.0
    DASHBOARD_PORT=8420          (or any port you prefer)

Before doing that:
  1. Run `python scripts/set_dashboard_password.py` FIRST. Binding to
     0.0.0.0 without a password set means literally anyone on your
     network can open and use the full dashboard — approvals,
     permissions, the kill switch, everything — with zero login. See
     agent/security/dashboard_auth.py.
  2. Even with a password set, plain HTTP sends that password over the
     network in the clear on every login. On a home network you
     personally control, that's a real but bounded risk (anyone
     already on your Wi-Fi with a packet sniffer). On anything less
     trusted, it's not acceptable. Two ways to fix that:
       a) Generate a local self-signed certificate
          (scripts/generate_dashboard_selfsigned_cert.py) and set
          DASHBOARD_SSL_KEYFILE / DASHBOARD_SSL_CERTFILE below — your
          browser/phone will warn about an untrusted certificate once;
          that's expected for a self-signed cert and safe to accept
          for your own server.
       b) Put this behind a VPN (Tailscale, WireGuard) instead of
          exposing it on your LAN/router directly — this project
          doesn't set that up for you, but it's the more robust
          option if you're going to do this regularly, since it
          encrypts everything AND means the dashboard is never
          reachable by anyone not on your private VPN, regardless of
          network.

Optional TLS (leave both blank to serve plain HTTP, as before):
    DASHBOARD_SSL_KEYFILE=database/dashboard.key
    DASHBOARD_SSL_CERTFILE=database/dashboard.crt

Usage:
    python scripts/run_dashboard.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn
from dotenv import load_dotenv

load_dotenv()

DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8420"))
SSL_KEYFILE = os.getenv("DASHBOARD_SSL_KEYFILE", "").strip() or None
SSL_CERTFILE = os.getenv("DASHBOARD_SSL_CERTFILE", "").strip() or None

if __name__ == "__main__":
    scheme = "https" if (SSL_KEYFILE and SSL_CERTFILE) else "http"
    print(f"Starting NightWalker dashboard at {scheme}://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    if DASHBOARD_HOST != "127.0.0.1":
        print("\n[!] Bound beyond localhost — reachable from other devices on your network.")
        from agent.security.dashboard_auth import has_password_set
        if not has_password_set():
            print("[!] NO PASSWORD IS SET. Anyone reaching this address has full, unauthenticated")
            print("    control of the dashboard. Run scripts/set_dashboard_password.py first.")
        if scheme == "http":
            print("[!] Serving plain HTTP — your password travels unencrypted on login. See this")
            print("    file's docstring for how to add TLS or use a VPN instead.")

    print("\n(Press Ctrl+C to stop)")
    uvicorn.run(
        "dashboard.app:app",
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        reload=False,
        ssl_keyfile=SSL_KEYFILE,
        ssl_certfile=SSL_CERTFILE,
    )
