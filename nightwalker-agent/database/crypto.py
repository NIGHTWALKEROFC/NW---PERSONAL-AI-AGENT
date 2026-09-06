"""
database/crypto.py

Application-level field encryption using Fernet (symmetric, from the
`cryptography` library — pure Python, no native build tools needed,
which is why this was chosen over SQLCipher for a Windows target).

*** WHAT THIS DOES AND DOES NOT PROTECT AGAINST — READ THIS ***

This encrypts the CONTENT of sensitive fields (profile data, message
text, corrections, sensitive flags, contact memory content) before
they're written to database/nightwalker.db. Structural data needed for
querying — contact names, roles, categories, timestamps, memory-type
labels — stays in plaintext, because encrypting them would break the
ability to search/filter/join on them without a much bigger redesign
(deterministic encryption, which is weaker).

The encryption key lives in a SEPARATE file: database/secret.key.
This is real, useful protection for one specific scenario: if the
.db file alone gets copied somewhere it shouldn't (an accidental cloud
backup sync, a copied folder, a lost drive) — WITHOUT the key file —
its sensitive content is unreadable.

It does NOT protect you if someone has access to BOTH files, which is
the normal case for anyone with access to this laptop. This is not
whole-disk encryption and it is not a substitute for securing the
machine itself (a login password, disk encryption like BitLocker).
It is one specific, honest layer: protecting the database file in
isolation.

The key file itself is gitignored and must never be committed, shared,
or backed up alongside the database file it protects — keeping them
together defeats the purpose entirely.
"""

import os
import stat

from cryptography.fernet import Fernet, InvalidToken

KEY_PATH = os.path.join(os.path.dirname(__file__), "secret.key")

_fernet_instance = None


def _load_or_create_key() -> bytes:
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()

    key = Fernet.generate_key()
    # Phase 15 (security audit) fix: this file used to be written with default
    # permissions (typically world-readable, e.g. 644, on POSIX systems) — on a
    # laptop with more than one local user account, any of them could read the
    # encryption key. Restricting to owner-only read/write at creation time closes
    # that gap. On Windows this has limited effect (POSIX permission bits don't map
    # cleanly), so the real protection on Windows is still whatever protects the
    # laptop itself (a login password, disk encryption) — same honesty as this
    # module's own docstring already states about what this layer does and doesn't
    # cover.
    fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(_load_or_create_key())
    return _fernet_instance


def encrypt_text(plaintext: str | None) -> str | None:
    """Returns an encrypted token as a string, ready to store in a TEXT column. None passes through unchanged."""
    if plaintext is None:
        return None
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(token: str | None) -> str | None:
    """
    Decrypts a token produced by encrypt_text(). None passes through unchanged.

    If the value can't be decrypted (e.g. it's old plaintext data from
    before Phase 8 that hasn't been migrated yet via
    scripts/encrypt_existing_data.py), this returns it UNCHANGED rather
    than crashing — so an un-migrated database doesn't hard-fail every
    read, it just means that particular field is still in plaintext
    until migration runs.
    """
    if token is None:
        return None
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return token
