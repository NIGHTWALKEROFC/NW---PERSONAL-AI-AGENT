"""
connectors/meta_shared.py

Signature verification shared by both Meta-owned connectors —
Instagram (connectors/instagram/) and WhatsApp (connectors/whatsapp/).
Both platforms use the exact same scheme (Meta's own docs describe it
identically for each): the X-Hub-Signature-256 header is
"sha256=<hexdigest>", where the digest is HMAC-SHA256 of the RAW
(unparsed) request body, keyed with the app's App Secret. Factored out
once rather than duplicated in each adapter, since drift between two
copies of security-critical code is exactly the kind of bug that's
easy to introduce and hard to notice.
"""

import hmac
import hashlib


def verify_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """
    Returns True only if signature_header is a valid "sha256=..."
    signature of raw_body under app_secret. Uses hmac.compare_digest
    for the final comparison (constant-time) rather than `==`, so the
    comparison itself can't leak timing information about how much of
    the signature matched.
    """
    if not signature_header or not app_secret or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)
