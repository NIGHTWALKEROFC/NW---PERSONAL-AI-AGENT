"""
scripts/benchmark_model.py

Times a few sample prompts against the currently active model so you
have real numbers for YOUR hardware (RTX 5050, 8GB VRAM) rather than
numbers from a review site.

Usage:
    python scripts/benchmark_model.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.brain.model_client import ModelClient, ModelClientError
from agent.brain.model_manager import get_active_model

SAMPLE_PROMPTS = [
    "Say hello in one short sentence.",
    "List three benefits of local-first software, briefly.",
    "Write a two-sentence summary of what a personal AI agent does.",
]


def rough_tokens_per_second(text: str, elapsed_seconds: float) -> float:
    # Rough estimate only — good enough to compare models/settings on this machine.
    approx_tokens = max(len(text.split()), 1)
    return approx_tokens / elapsed_seconds if elapsed_seconds > 0 else 0.0


def main():
    model_name = get_active_model()
    client = ModelClient(model_name)

    if not client.is_available():
        print("[!] Cannot reach Ollama. Is it running?")
        return

    print(f"Benchmarking: {model_name}\n")

    for prompt in SAMPLE_PROMPTS:
        messages = [{"role": "user", "content": prompt}]
        try:
            result = client.chat(messages)
        except ModelClientError as e:
            print(f"  [error] {e}")
            continue

        tps = rough_tokens_per_second(result["content"], result["elapsed_seconds"])
        print(f"Prompt: {prompt}")
        print(f"  Time: {result['elapsed_seconds']:.2f}s   ~{tps:.1f} tok/s (rough estimate)")
        print(f"  Reply: {result['content'][:120]}...\n")


if __name__ == "__main__":
    main()
