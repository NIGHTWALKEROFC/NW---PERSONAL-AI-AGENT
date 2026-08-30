"""
connectors/base.py

The platform adapter architecture from spec section 11:

    agent core -> platform adapter -> official API / authorized automation -> platform

The agent core (reply pipeline, permission engine, timing engine)
never talks to a specific platform directly — it only knows about this
interface. Adding a new platform later means writing one new adapter
class, not touching the agent's decision-making logic at all.

Every adapter must use an official API or explicitly authorized
automation. Nothing implementing this interface may do: captcha
solving, ban evasion, fingerprint spoofing, credential theft, or any
form of unauthorized access — per the spec's explicit prohibitions.
"""

from abc import ABC, abstractmethod


class IncomingMessage:
    """A normalized incoming message, regardless of which platform it came from."""

    def __init__(self, platform_user_id: str, display_name: str, text: str, message_id: str, timestamp: str):
        self.platform_user_id = platform_user_id  # the platform's own ID for this sender (e.g. a Telegram chat ID)
        self.display_name = display_name          # a human-readable name/username, for contact resolution
        self.text = text
        self.message_id = message_id
        self.timestamp = timestamp


class PlatformAdapter(ABC):
    """Every platform connector implements this interface."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Short lowercase identifier, e.g. 'telegram'. Used for contact.platform and permission logging."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if credentials are present and the adapter is ready to use."""
        ...

    @abstractmethod
    def fetch_incoming_messages(self) -> list[IncomingMessage]:
        """
        Returns new incoming messages since the last call. Implementations
        are responsible for their own offset/cursor tracking so the same
        message is never returned twice.
        """
        ...

    @abstractmethod
    def send_message(self, platform_user_id: str, text: str) -> bool:
        """Sends a message to the given platform-specific recipient. Returns True on success."""
        ...
