"""
agent/actions/action_dispatcher.py

The one place in the whole project where a real external action
actually happens. Everything upstream (reply pipeline, permission
engine, timing engine, approval queue) only ever decides WHAT should
happen and WHETHER it's allowed — this is where an allowed decision
becomes a real, sent message.

Called from two places:
1. connectors/telegram's polling loop, when the reply pipeline returns
   status="ready" (AUTO/SUGGEST permission, timing allowed).
2. The approval queue, when a pending approval is resolved as
   "approved" or "edited" (dashboard or CLI).

This is also where a sent reply finally gets persisted to short-term
memory — every earlier phase's reply generation was explicitly NOT
persisted because it was only ever a preview. Once a message is
actually sent for real, it IS a real conversation turn, so it belongs
in memory like any other.
"""

from connectors.registry import get_adapter
from database.contact_store import get_contact_by_name, add_contact_memory
from database.memory_store import log_message
from agent.security.security_events import log_event


class DispatchError(Exception):
    """Raised when a send couldn't be completed — missing platform info, adapter not configured, or the send itself failed."""


def dispatch_send(contact_id: int, text: str) -> bool:
    """
    Looks up the contact's platform + platform-specific ID, sends the
    message via the right adapter, and persists it as a real sent
    message in short-term memory. Raises DispatchError on any failure
    rather than failing silently — a failed send should never look
    like a successful one.
    """
    from database.db import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if row is None:
        raise DispatchError(f"No contact found with id {contact_id}.")

    contact = dict(row)
    platform = contact.get("platform")
    platform_id = contact.get("platform_id")

    if not platform or not platform_id:
        raise DispatchError(
            f"Contact '{contact['name']}' has no platform/platform_id on record — "
            "this usually means the contact was created by conversation import, not by "
            "a live platform connector, so there's nowhere to actually send this."
        )

    adapter = get_adapter(platform)
    if adapter is None:
        raise DispatchError(f"No connector registered for platform '{platform}'.")

    if not adapter.is_configured():
        raise DispatchError(f"The '{platform}' connector isn't configured (missing credentials in .env).")

    success = adapter.send_message(platform_id, text)
    if not success:
        raise DispatchError(f"Sending via '{platform}' reported failure.")

    log_message("agent", text, contact_id=contact_id, memory_layer="short_term")
    log_event("message_sent", f"platform={platform}, contact_id={contact_id}")

    return True


def dispatch_send_by_name(contact_name: str, text: str) -> bool:
    """Convenience wrapper for callers that only have the contact's name, not id."""
    contact = get_contact_by_name(contact_name)
    if contact is None:
        raise DispatchError(f"No contact named '{contact_name}' found.")
    return dispatch_send(contact["id"], text)
