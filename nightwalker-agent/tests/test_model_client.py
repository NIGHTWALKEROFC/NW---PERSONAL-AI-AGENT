"""
tests/test_model_client.py

Minimal smoke test for Phase 1. Requires Ollama to be running locally
with the active model already pulled.

Run with:
    python -m pytest tests/
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient
from agent.brain.model_manager import get_active_model


def test_ollama_is_reachable():
    client = ModelClient(get_active_model())
    assert client.is_available(), (
        "Ollama is not reachable at the configured host. "
        "Start Ollama and make sure the model is pulled before running tests."
    )


def test_basic_chat_response():
    client = ModelClient(get_active_model())
    if not client.is_available():
        return  # skip silently if Ollama isn't up; not a code failure

    result = client.chat([{"role": "user", "content": "Reply with just: ok"}])
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0
