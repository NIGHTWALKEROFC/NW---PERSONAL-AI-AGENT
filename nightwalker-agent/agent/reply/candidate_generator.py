"""
agent/reply/candidate_generator.py

Implements the spec's "generate multiple internal candidates" step.
Rather than asking the model once and taking whatever comes back, this
asks 3 times at different temperatures — low (more predictable/safe),
medium, and higher (more varied phrasing) — so the selector in
candidate_selector.py has real options to choose between instead of
picking the only draft that exists.

These candidates are internal only. Nothing here sends or displays
anything by itself — that's the caller's job (see pipeline.py).
"""

from agent.brain.model_client import ModelClient, ModelClientError

DEFAULT_TEMPERATURES = [0.3, 0.7, 1.0]


def generate_candidates(
    context_messages: list[dict],
    incoming_message: str,
    model_name: str,
    temperatures: list[float] | None = None,
) -> list[dict]:
    """
    context_messages: from context_builder.build_context_messages() —
    system prompt + recent history, NOT including the incoming message.

    Returns a list of {"text": str, "temperature": float} — a candidate
    is skipped (not included) if that particular call fails, so a
    single Ollama hiccup doesn't kill the whole batch.
    """
    temperatures = temperatures or DEFAULT_TEMPERATURES
    client = ModelClient(model_name)

    messages = context_messages + [{"role": "user", "content": incoming_message}]

    candidates = []
    for temp in temperatures:
        try:
            result = client.chat(messages, options={"temperature": temp})
        except ModelClientError:
            continue  # skip this one, keep trying the others
        text = result["content"].strip()
        if text:
            candidates.append({"text": text, "temperature": temp})

    return candidates
