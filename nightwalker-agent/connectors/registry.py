"""
connectors/registry.py

Maps a platform name (as stored in contacts.platform) to its adapter.
This is what lets agent/actions/action_dispatcher.py send a message
without knowing or caring which specific platform it's going to — it
just asks the registry for the right adapter.

Adding a new platform later means writing one adapter class and adding
one line here — nothing in the agent core changes. Phase 13 added
Instagram and WhatsApp this way; Telegram's own registration (Phase
10) needed no changes at all.
"""

from connectors.telegram.telegram_adapter import TelegramAdapter
from connectors.instagram.instagram_adapter import InstagramAdapter
from connectors.whatsapp.whatsapp_adapter import WhatsAppAdapter

_ADAPTERS = {
    "telegram": TelegramAdapter,
    "instagram": InstagramAdapter,
    "whatsapp": WhatsAppAdapter,
}


def get_adapter(platform_name: str):
    """Returns a fresh adapter instance for the given platform, or None if unrecognized."""
    adapter_class = _ADAPTERS.get(platform_name)
    return adapter_class() if adapter_class else None


def list_platforms() -> list[str]:
    return list(_ADAPTERS.keys())
