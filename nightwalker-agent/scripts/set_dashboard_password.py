"""
scripts/set_dashboard_password.py

Sets (or changes) the dashboard's login password — see
agent/security/dashboard_auth.py for the full explanation of why this
is opt-in and CLI-only rather than a web form: before a password
exists, there's nothing to check a web login attempt against, and
after one exists, letting the dashboard itself change its own password
over the network is exactly the kind of thing that should require
being at the actual machine instead.

Running this for the FIRST time turns on authentication for the whole
dashboard, on every device, immediately — see this file's own printed
confirmation and agent/security/dashboard_auth.py's "OPT-IN, NOT
FORCED" section.

Changing the password (running this again) revokes every existing
session — every device currently logged in will need to log back in
with the new password.

Usage:
    python scripts/set_dashboard_password.py
"""

import sys
import os
import getpass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.security.dashboard_auth import has_password_set, set_password
from agent.security.security_events import log_event


def main():
    first_time = not has_password_set()

    if first_time:
        print("No dashboard password is set yet. Setting one now will turn on")
        print("login for the ENTIRE dashboard — including on this laptop — from")
        print("now on. If you only ever use this on one trusted machine and never")
        print("plan to access it remotely, you don't need to do this at all.")
    else:
        print("Changing the dashboard password. This will log out every device")
        print("currently signed in — you'll need to log back in everywhere,")
        print("including here, with the new password.")

    confirm = input("\nContinue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled — nothing changed.")
        return

    while True:
        password = getpass.getpass("\nNew password (min 8 characters, hidden as you type): ")
        if len(password) < 8:
            print("Too short — try again.")
            continue
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("Didn't match — try again.")
            continue
        break

    set_password(password)
    log_event("dashboard_password_changed", "set via scripts/set_dashboard_password.py")

    if first_time:
        print("\nDashboard password set. Authentication is now ON for every device.")
    else:
        print("\nDashboard password changed. All previous sessions have been logged out.")


if __name__ == "__main__":
    main()
