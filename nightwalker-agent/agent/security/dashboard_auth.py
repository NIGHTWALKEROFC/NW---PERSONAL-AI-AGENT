"""
agent/security/dashboard_auth.py

Phase 14's authentication layer for the dashboard, added because
multi-device access means the dashboard can no longer rely solely on
"nobody outside your machine can reach it" — its security model since
Phase 1. See scripts/run_dashboard.py and dashboard/auth_middleware.py
for how this gets applied.

*** OPT-IN, NOT FORCED ***
If you never run scripts/set_dashboard_password.py, has_password_set()
returns False and dashboard/auth_middleware.py lets every request
through exactly as it always has — nothing about existing single-
device usage changes unless you deliberately turn this on. The moment
a password IS set, every dashboard request (including on the laptop
itself) requires a valid session — there's no way to have auth apply
only to "other" devices, since the dashboard can't distinguish which
device is asking.

*** PASSWORD HASHING ***
PBKDF2-HMAC-SHA256 with a random 16-byte salt and 600,000 iterations
(OWASP's 2023 minimum recommendation for PBKDF2-SHA256), via Python's
stdlib hashlib — no new dependency needed for this. This is NOT the
same key/mechanism as database/crypto.py's Fernet key (that encrypts
message content at rest; this authenticates a login). The two are
unrelated and a compromise of one does not compromise the other.

*** SESSIONS ***
A session is a random 32-byte URL-safe token (session_id) stored
server-side in the dashboard_sessions table with an expiry — NOT a
signed stateless cookie — specifically so a session can be positively
revoked (the Security page's "Log out all devices", and the kill
switch, both do this). The cookie itself only carries the token;
nothing about it is trusted without a live, non-revoked, non-expired
row in the table.

*** BRUTE-FORCE LOCKOUT ***
login_attempts records every attempt (success or failure) keyed by
source IP. is_locked_out() blocks further attempts from an IP with too
many recent failures. This is IP-based, so it's only as good as the
IP information available — behind a tunnel (ngrok, Cloudflare Tunnel)
every request may appear to come from the tunnel's own address rather
than the real client, which would lock out ALL devices together after
enough failures from any one of them. Documented here rather than
silently assumed to work perfectly.

*** WHAT THIS DOES NOT DO ***
No CSRF tokens (login and every other POST form in this dashboard
already had none — Phase 8 through 13's approval/permission/kill-
switch forms are exactly as unprotected against CSRF as this login
form is; adding CSRF here alone would be inconsistent, not a real fix).
No account lockout notification, no password reset flow (there's only
one account; recovery is re-running scripts/set_dashboard_password.py
on the laptop itself, which is trusted by definition since it's the
same trust boundary the whole rest of this project already relies on).
No rate limiting beyond the IP-based lockout above.
"""

import os
import hmac
import hashlib
import secrets
import datetime

from database.db import get_connection

PBKDF2_ITERATIONS = 600_000
DEFAULT_SESSION_TTL_HOURS = int(os.getenv("DASHBOARD_SESSION_TTL_HOURS", "720"))  # 30 days
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 15


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _now_str() -> str:
    return _now().isoformat() + "Z"


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def has_password_set() -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM dashboard_auth WHERE id = 1").fetchone()
    return row is not None


def set_password(new_password: str) -> None:
    """
    Sets or overwrites the single dashboard password. Also revokes
    every existing session — changing the password should mean every
    device currently logged in has to log back in with the new one,
    the same expectation as changing a password anywhere else.
    """
    if len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    salt = secrets.token_bytes(16)
    password_hash = _hash_password(new_password, salt)

    conn = get_connection()
    conn.execute(
        "INSERT INTO dashboard_auth (id, password_hash, salt, updated_at) VALUES (1, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET password_hash = excluded.password_hash, "
        "salt = excluded.salt, updated_at = excluded.updated_at",
        (password_hash, salt.hex(), _now_str()),
    )
    conn.commit()
    revoke_all_sessions()


def verify_password(password: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT password_hash, salt FROM dashboard_auth WHERE id = 1").fetchone()
    if row is None:
        return False
    salt = bytes.fromhex(row["salt"])
    candidate_hash = _hash_password(password, salt)
    # Constant-time comparison — a login check is exactly the kind of comparison
    # where a timing side-channel could otherwise leak how much of the password matched.
    return hmac.compare_digest(candidate_hash, row["password_hash"])


def create_session(device_label: str = "", ttl_hours: int = DEFAULT_SESSION_TTL_HOURS) -> str:
    session_id = secrets.token_urlsafe(32)
    now = _now()
    expires_at = now + datetime.timedelta(hours=ttl_hours)

    conn = get_connection()
    conn.execute(
        "INSERT INTO dashboard_sessions (session_id, created_at, expires_at, last_seen_at, device_label, revoked) "
        "VALUES (?, ?, ?, ?, ?, 0)",
        (session_id, _now_str(), expires_at.isoformat() + "Z", _now_str(), device_label),
    )
    conn.commit()
    return session_id


def validate_session(session_id: str) -> bool:
    """Also touches last_seen_at on success, so the Security page can show real activity, not just creation time."""
    if not session_id:
        return False

    conn = get_connection()
    row = conn.execute(
        "SELECT expires_at, revoked FROM dashboard_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None or row["revoked"]:
        return False

    expires_at = datetime.datetime.fromisoformat(row["expires_at"].rstrip("Z"))
    if _now() > expires_at:
        return False

    conn.execute("UPDATE dashboard_sessions SET last_seen_at = ? WHERE session_id = ?", (_now_str(), session_id))
    conn.commit()
    return True


def revoke_session(session_id: str) -> bool:
    conn = get_connection()
    cur = conn.execute("UPDATE dashboard_sessions SET revoked = 1 WHERE session_id = ?", (session_id,))
    conn.commit()
    return cur.rowcount > 0


def revoke_all_sessions() -> int:
    conn = get_connection()
    cur = conn.execute("UPDATE dashboard_sessions SET revoked = 1 WHERE revoked = 0")
    conn.commit()
    return cur.rowcount


def list_active_sessions() -> list[dict]:
    """Active = not revoked and not expired. Used by the Security page."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT session_id, created_at, expires_at, last_seen_at, device_label "
        "FROM dashboard_sessions WHERE revoked = 0 ORDER BY last_seen_at DESC"
    ).fetchall()

    now = _now()
    active = []
    for row in rows:
        expires_at = datetime.datetime.fromisoformat(row["expires_at"].rstrip("Z"))
        if now <= expires_at:
            active.append({
                "session_id": row["session_id"],
                "session_id_short": row["session_id"][:8] + "…",
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "last_seen_at": row["last_seen_at"],
                "device_label": row["device_label"] or "(unlabeled device)",
            })
    return active


def record_login_attempt(source_ip: str, success: bool) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO login_attempts (source_ip, attempted_at, success) VALUES (?, ?, ?)",
        (source_ip, _now_str(), 1 if success else 0),
    )
    conn.commit()


def is_locked_out(source_ip: str) -> bool:
    conn = get_connection()
    window_start = (_now() - datetime.timedelta(minutes=LOCKOUT_WINDOW_MINUTES)).isoformat() + "Z"
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM login_attempts "
        "WHERE source_ip = ? AND success = 0 AND attempted_at >= ?",
        (source_ip, window_start),
    ).fetchone()
    return row["c"] >= LOCKOUT_MAX_ATTEMPTS
