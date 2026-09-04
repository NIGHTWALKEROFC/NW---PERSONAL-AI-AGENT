"""
scripts/run_webhook_server.py

Runs webhooks/webhook_server.py — the standalone, minimal receiver for
Instagram/WhatsApp webhook deliveries. See that file's docstring for
why this is a SEPARATE process from the dashboard, not a route added
to it.

*** THIS BINDS TO 0.0.0.0, NOT 127.0.0.1 — READ BEFORE RUNNING ***
Unlike the dashboard (scripts/run_dashboard.py, 127.0.0.1 only), Meta
needs to reach this over the public internet, so it has to listen on
all interfaces. On your own machine behind a home router, 0.0.0.0
alone does NOT make this internet-reachable by itself — you also need
either:
  - a tunnel tool (ngrok, Cloudflare Tunnel) pointing at this port, for
    testing — gives you a temporary public HTTPS URL, or
  - real hosting (a VPS, a cloud instance) with a domain and TLS
    certificate, for anything beyond testing.
Meta requires HTTPS for the callback URL — plain http:// is rejected.
A tunnel tool provides that HTTPS layer for you during development.

Only two routes exist on this whole app (see webhook_server.py), and
neither can do anything except write a row into webhook_inbox after
verifying Meta's signature — but it's still the one thing in this
project meant to be reachable from the internet, so don't leave it
running longer than you need to while testing, and don't reuse its
port for anything else.

Usage:
    python scripts/run_webhook_server.py
    (then point a tunnel at the port it prints, and configure that
    tunnel's HTTPS URL + your chosen verify token in the Meta app
    dashboard's webhook settings, for each platform you're using)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uvicorn

WEBHOOK_SERVER_PORT = int(os.getenv("WEBHOOK_SERVER_PORT", "8001"))

if __name__ == "__main__":
    print(f"Starting webhook receiver on 0.0.0.0:{WEBHOOK_SERVER_PORT}")
    print("This is NOT reachable from the internet by itself — see this file's")
    print("docstring for tunnel/hosting setup.")
    print("Routes: /webhooks/instagram, /webhooks/whatsapp\n")
    uvicorn.run("webhooks.webhook_server:app", host="0.0.0.0", port=WEBHOOK_SERVER_PORT)
