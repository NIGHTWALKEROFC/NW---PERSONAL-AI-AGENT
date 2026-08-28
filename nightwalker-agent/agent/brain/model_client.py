"""
agent/brain/model_client.py

Thin wrapper around the local Ollama HTTP API.
No cloud calls. No API keys. Talks only to http://localhost:11434 (or
whatever OLLAMA_HOST is set to) by default.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


class ModelClientError(Exception):
    """Raised when the local model server can't be reached or errors out."""


class ModelClient:
    def __init__(self, model_name: str, host: str = OLLAMA_HOST, timeout: int = OLLAMA_TIMEOUT):
        self.model_name = model_name
        self.host = host.rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check that Ollama is running and reachable before doing anything else."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def chat(self, messages: list[dict], stream: bool = False) -> dict:
        """
        Send a chat-style request to Ollama.

        messages: list of {"role": "system"|"user"|"assistant", "content": str}
        Returns: {"content": str, "elapsed_seconds": float, "raw": dict}
        """
        if not self.is_available():
            raise ModelClientError(
                f"Cannot reach Ollama at {self.host}. "
                "Make sure Ollama is running (it usually runs as a background service)."
            )

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }

        start = time.time()
        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ModelClientError(f"Ollama request failed: {e}") from e

        elapsed = time.time() - start
        data = resp.json()
        content = data.get("message", {}).get("content", "")

        return {
            "content": content,
            "elapsed_seconds": elapsed,
            "raw": data,
        }
