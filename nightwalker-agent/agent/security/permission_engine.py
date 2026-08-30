"""
agent/security/permission_engine.py

The permission system from spec section 10:
    AUTO / ASK / SUGGEST / DISABLED / NEVER

per action type, configurable from the dashboard (Permissions page).

An action type not found in config gets a safe default of "ASK"
rather than silently allowing it — an unrecognized action should
never be treated as pre-approved.

This module only stores and retrieves levels — it doesn't decide what
to DO with a given level for a given action. That decision belongs to
whatever is about to perform the action (e.g. agent/reply/pipeline.py
checking "send_normal_reply" before finalizing a reply).
"""

import json
import os

PERMISSIONS_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "permissions_config.json"
)

VALID_LEVELS = {"AUTO", "ASK", "SUGGEST", "DISABLED", "NEVER"}

DEFAULT_LEVEL_FOR_UNKNOWN_ACTION = "ASK"


def load_permissions() -> dict:
    with open(PERMISSIONS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_permissions(permissions: dict) -> None:
    with open(PERMISSIONS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(permissions, f, indent=2)


def get_permission(action_type: str) -> str:
    permissions = load_permissions()
    return permissions.get(action_type, DEFAULT_LEVEL_FOR_UNKNOWN_ACTION)


def set_permission(action_type: str, level: str) -> None:
    if level not in VALID_LEVELS:
        raise ValueError(f"Invalid permission level '{level}'. Must be one of: {sorted(VALID_LEVELS)}")
    permissions = load_permissions()
    permissions[action_type] = level
    save_permissions(permissions)
