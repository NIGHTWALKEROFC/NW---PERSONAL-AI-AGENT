"""
agent/brain/model_manager.py

Keeps the active model name in config, not hardcoded in code.
Later phases (benchmarking, auto-selection) will extend this file —
for Phase 1 it just reads/writes config/model_config.json.
"""

import json
import os

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "model_config.json"
)


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_active_model() -> str:
    """Returns the currently configured model name."""
    return _load_config()["active_model"]


def get_context_length() -> int:
    return _load_config().get("context_length", 8192)


def list_candidates() -> list[dict]:
    return _load_config().get("candidates", [])


def set_active_model(model_name: str) -> None:
    """
    Switch the active model. Does NOT verify the model is pulled in Ollama —
    that check belongs to the caller (e.g. run_agent.py or a future
    dashboard action) before actually using it.
    """
    config = _load_config()
    known_names = [c["name"] for c in config.get("candidates", [])]
    if model_name not in known_names:
        config.setdefault("candidates", []).append(
            {"name": model_name, "notes": "Added manually."}
        )
    config["active_model"] = model_name
    _save_config(config)
