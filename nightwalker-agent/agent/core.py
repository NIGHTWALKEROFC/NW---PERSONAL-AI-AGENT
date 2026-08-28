"""
agent/core.py

Phase 4 update: conversation turns now persist to the short-term
memory layer (database/nightwalker.db) instead of living only in an
in-memory list that vanished when the script exited. On startup, the
agent preloads its recent short-term history so a conversation can
pick back up across separate runs of run_agent.py.

Still no personality profile applied to replies, no per-contact
routing, no reply-candidate generation or safety checks — those are
Phase 5+. This file is still the minimal loop; it just no longer
forgets everything the moment you close the terminal.
"""

from agent.brain.model_client import ModelClient, ModelClientError
from agent.brain.model_manager import get_active_model
from database.memory_store import add_short_term_message, get_recent_short_term

DEFAULT_SYSTEM_PROMPT = (
    "You are a private local assistant running entirely on the user's own "
    "laptop. Keep responses natural and concise."
)

# How many past short-term messages to preload as context on startup.
HISTORY_PRELOAD_LIMIT = 20


class Agent:
    def __init__(self, system_prompt: str = DEFAULT_SYSTEM_PROMPT, contact_id: int | None = None):
        self.model_name = get_active_model()
        self.client = ModelClient(self.model_name)
        self.system_prompt = system_prompt
        self.contact_id = contact_id  # None = general/standalone conversation, not tied to a contact
        self.history: list[dict] = [{"role": "system", "content": self.system_prompt}]
        self._preload_recent_history()

    def _preload_recent_history(self) -> None:
        recent = get_recent_short_term(limit=HISTORY_PRELOAD_LIMIT, contact_id=self.contact_id)
        for msg in recent:
            # Stored roles are 'me'/'agent' for clarity in the database;
            # translate to the 'user'/'assistant' roles the model API expects.
            role = "user" if msg["role"] == "me" else "assistant"
            self.history.append({"role": role, "content": msg["content"]})

    def send(self, user_message: str) -> str:
        """
        Send a message, get a reply, keep it in in-memory history for
        this call's context window, AND persist both sides to
        short-term memory so it survives a restart.
        """
        self.history.append({"role": "user", "content": user_message})
        add_short_term_message("me", user_message, contact_id=self.contact_id)

        try:
            result = self.client.chat(self.history)
        except ModelClientError as e:
            # Fail loud and clear rather than silently returning nothing.
            # Not persisted — an error isn't part of the real conversation.
            return f"[agent error] {e}"

        reply = result["content"]
        self.history.append({"role": "assistant", "content": reply})
        add_short_term_message("agent", reply, contact_id=self.contact_id)
        return reply

    def reset(self) -> None:
        """
        Clears in-memory history for this session only. Does NOT delete
        persisted short-term memory from the database — use
        database.memory_store.clear_short_term() explicitly for that.
        """
        self.history = [{"role": "system", "content": self.system_prompt}]
