"""
automation/desktop/actions.py

Defines the shape of a desktop action request. Pure data — no GUI
library dependency here at all, so this file is fully testable
anywhere, including this sandbox.

expected_state_description is required for 'click' and 'type_text'
(the higher-risk actions) — per spec section 16, the screen must be
verified against an expectation before those proceed. It's optional
for 'open_app' and 'read_screen' since there's less to verify before
a lower-risk action.
"""

from dataclasses import dataclass, field

VALID_ACTION_TYPES = {"open_app", "click", "type_text", "read_screen"}

# Maps an action type to the permission_engine action key that gates it.
ACTION_PERMISSION_MAP = {
    "open_app": "desktop_open_app",
    "click": "desktop_click",
    "type_text": "desktop_type",
    "read_screen": "desktop_read_screen",
}

# Action types where skipping screen verification is not allowed —
# these are the ones that can do real, hard-to-undo things.
REQUIRES_VERIFICATION = {"click", "type_text"}


@dataclass
class DesktopAction:
    action_type: str
    params: dict = field(default_factory=dict)
    expected_state_description: str = ""

    def __post_init__(self):
        if self.action_type not in VALID_ACTION_TYPES:
            raise ValueError(f"Invalid action_type '{self.action_type}'. Must be one of: {sorted(VALID_ACTION_TYPES)}")
        if self.action_type in REQUIRES_VERIFICATION and not self.expected_state_description.strip():
            raise ValueError(
                f"'{self.action_type}' requires expected_state_description — "
                "describe what the screen should look like right now before this action proceeds."
            )

    def permission_key(self) -> str:
        return ACTION_PERMISSION_MAP[self.action_type]
