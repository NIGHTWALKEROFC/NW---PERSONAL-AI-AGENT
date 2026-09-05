"""
scripts/generate_dashboard_selfsigned_cert.py

Generates a self-signed TLS certificate + private key for serving the
dashboard over HTTPS on your local network — see scripts/run_dashboard.py's
docstring for why this matters once you're binding beyond 127.0.0.1
for multi-device access.

Uses the `cryptography` package, already a dependency of this project
(database/crypto.py uses it too, for unrelated reasons — this is a
completely separate use of the same library, not the same key).

The certificate covers "localhost", "127.0.0.1", and any hostnames/IPs
you pass on the command line (e.g. your laptop's LAN IP, so a phone on
the same network can connect to it by address). Your browser/phone
will show an "untrusted certificate" warning the first time you
connect — that's expected and correct for a self-signed certificate;
accepting it is safe because you generated it yourself, on your own
machine, moments ago.

Valid for 825 days (the longest lifetime that stays broadly compatible
with browser certificate-lifetime limits at the time this was
written). Re-run this script to generate a new one once it expires.

Usage:
    python scripts/generate_dashboard_selfsigned_cert.py [extra hostname/IP ...]

    # e.g. if your laptop's LAN IP is 192.168.1.42:
    python scripts/generate_dashboard_selfsigned_cert.py 192.168.1.42

Then add to .env:
    DASHBOARD_SSL_KEYFILE=database/dashboard.key
    DASHBOARD_SSL_CERTFILE=database/dashboard.crt
"""

import sys
import os
import datetime
import ipaddress

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "database")
KEY_PATH = os.path.join(OUTPUT_DIR, "dashboard.key")
CERT_PATH = os.path.join(OUTPUT_DIR, "dashboard.crt")


def _build_san_entries(extra_hosts: list[str]) -> list:
    entries = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    for host in extra_hosts:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            entries.append(x509.DNSName(host))
    return entries


def generate(extra_hosts: list[str]) -> None:
    if os.path.exists(KEY_PATH) or os.path.exists(CERT_PATH):
        answer = input(
            f"{KEY_PATH} and/or {CERT_PATH} already exist. Overwrite? [y/N]: "
        ).strip().lower()
        if answer != "y":
            print("Cancelled — nothing changed.")
            return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "nightwalker-dashboard-local"),
    ])

    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(_build_san_entries(extra_hosts)), critical=False)
        .sign(key, hashes.SHA256())
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(KEY_PATH, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(CERT_PATH, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Wrote {KEY_PATH} and {CERT_PATH} (valid 825 days).")
    print("\nAdd to .env:")
    print(f"    DASHBOARD_SSL_KEYFILE={os.path.relpath(KEY_PATH)}")
    print(f"    DASHBOARD_SSL_CERTFILE={os.path.relpath(CERT_PATH)}")
    print("\nYour browser/phone will warn this certificate is untrusted the first")
    print("time you connect — that's expected for a self-signed cert; it's safe")
    print("to accept since you just generated it yourself.")


if __name__ == "__main__":
    generate(sys.argv[1:])
