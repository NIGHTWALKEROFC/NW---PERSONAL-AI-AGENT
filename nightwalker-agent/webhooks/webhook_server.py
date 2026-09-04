"""
webhooks/webhook_server.py

A SEPARATE, minimal FastAPI app whose only job is receiving Instagram
and WhatsApp webhook deliveries from Meta and enqueueing them into
database/webhook_inbox_store.py. Run via scripts/run_webhook_server.py.

*** WHY THIS IS NOT PART OF dashboard/app.py ***
Meta requires a webhook URL reachable from the public internet. The
control dashboard (dashboard/app.py) is deliberately bound to
127.0.0.1 only and has no authentication of its own — it relies
entirely on not being reachable from outside your machine. It also has
real consequential actions on it: the Approval Center, the security
kill switch, permission levels. Exposing that whole app to the
internet just to receive webhooks — even behind a tunnel — would
expose all of that too. This file exists so that ONLY a tiny,
purpose-built receiver with nothing sensitive on it is ever the thing
you expose publicly. Nothing in this file can change a permission,
approve an action, or touch the kill switch — the two routes here can
only write rows into webhook_inbox, nothing else.

*** Signature verification is not optional ***
Both POST routes verify Meta's X-Hub-Signature-256 header (via
connectors/meta_shared.py) before trusting any body content. An
unverified webhook endpoint accepts forged "messages" from anyone on
the internet who finds the URL — this is the one thing meant to be
exposed publicly, so it's the one thing that has to assume it's being
attacked.

*** Duplicate delivery handling ***
Meta's own docs say webhook deliveries can be retried/duplicated.
Before enqueueing, each handler checks whether a message_id has
already been enqueued (database/webhook_inbox_store.is_message_already_enqueued)
and skips it if so — this happens BEFORE the reply pipeline downstream
ever sees it, so a retried webhook delivery can never cause a
duplicate reply.

*** NOT TESTED against a real Meta webhook delivery ***
The GET-verification handshake and the POST handlers are exercised in
scripts/edge_case_tests.py using FastAPI's TestClient with synthetic
signed payloads. A real Meta app actually hitting this endpoint is
untested — same honesty as every other new integration point in this
project.
"""

import os

from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

from connectors.meta_shared import verify_signature
from connectors.instagram.instagram_adapter import parse_webhook_payload as parse_instagram_payload
from connectors.whatsapp.whatsapp_adapter import parse_webhook_payload as parse_whatsapp_payload
from database import webhook_inbox_store
from agent.security.security_events import log_event

load_dotenv()

app = FastAPI(title="NightWalker Webhook Receiver")


def _enqueue_parsed(platform: str, parsed_messages: list[dict]) -> int:
    enqueued = 0
    for msg in parsed_messages:
        if webhook_inbox_store.is_message_already_enqueued(platform, msg["message_id"]):
            continue
        webhook_inbox_store.enqueue(
            platform=platform,
            platform_user_id=msg["platform_user_id"],
            display_name=msg["display_name"],
            text=msg["text"],
            message_id=msg["message_id"],
            timestamp=msg["timestamp"],
        )
        enqueued += 1
    return enqueued


def _verify_challenge(request: Request, verify_token: str) -> Response:
    """Shared GET-verification handshake — identical scheme for both platforms per Meta's docs."""
    params = request.query_params
    if not verify_token:
        return Response(status_code=403, content="This platform's webhook verify token isn't configured in .env.")
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        return Response(status_code=200, content=params.get("hub.challenge", ""))
    return Response(status_code=403, content="Verification failed")


@app.get("/webhooks/instagram")
def verify_instagram_webhook(request: Request):
    return _verify_challenge(request, os.getenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", ""))


@app.post("/webhooks/instagram")
async def receive_instagram_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    app_secret = os.getenv("INSTAGRAM_APP_SECRET", "")

    if not verify_signature(raw_body, signature, app_secret):
        log_event("webhook_signature_rejected", "platform=instagram")
        return Response(status_code=403, content="Invalid signature")

    payload = await request.json()
    parsed = parse_instagram_payload(payload)
    count = _enqueue_parsed("instagram", parsed)
    if count:
        log_event("webhook_message_received", f"platform=instagram count={count}")
    return Response(status_code=200, content="OK")


@app.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(request: Request):
    return _verify_challenge(request, os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", ""))


@app.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256", "")
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "")

    if not verify_signature(raw_body, signature, app_secret):
        log_event("webhook_signature_rejected", "platform=whatsapp")
        return Response(status_code=403, content="Invalid signature")

    payload = await request.json()
    parsed = parse_whatsapp_payload(payload)
    count = _enqueue_parsed("whatsapp", parsed)
    if count:
        log_event("webhook_message_received", f"platform=whatsapp count={count}")
    return Response(status_code=200, content="OK")
