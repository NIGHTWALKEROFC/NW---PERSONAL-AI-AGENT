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

Phase 15 (performance audit) change: the 3 calls now run CONCURRENTLY
via a thread pool instead of one after another. ModelClient.chat() is
safe to call from multiple threads at once — each call opens its own
HTTP request with no shared mutable state between them (see
agent/brain/model_client.py). Whether this actually cuts wall-clock
time depends on your Ollama server's own configuration (OLLAMA_NUM_
PARALLEL — if it's 1, Ollama itself will still queue requests one at a
time internally, and this mainly saves the fixed per-request overhead
rather than inference time itself). It never makes things slower or
changes what gets generated — same 3 requests, same content, same
per-candidate failure tolerance (one bad call doesn't kill the batch)
— only how they're scheduled.
"""

from concurrent.futures import ThreadPoolExecutor

from agent.brain.model_client import ModelClient, ModelClientError

DEFAULT_TEMPERATURES = [0.3, 0.7, 1.0]


def _generate_one(client: ModelClient, messages: list[dict], temperature: float) -> dict | None:
    try:
        result = client.chat(messages, options={"temperature": temperature})
    except ModelClientError:
        return None  # skip this one, keep the others
    text = result["content"].strip()
    return {"text": text, "temperature": temperature} if text else None


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
    is skipped (not included) if that particular call fails or comes
    back empty, so a single Ollama hiccup doesn't kill the whole batch.
    Order matches `temperatures` (or DEFAULT_TEMPERATURES) regardless of
    which request actually finished first.
    """
    temperatures = temperatures or DEFAULT_TEMPERATURES
    client = ModelClient(model_name)
    messages = context_messages + [{"role": "user", "content": incoming_message}]

    with ThreadPoolExecutor(max_workers=len(temperatures)) as pool:
        results = list(pool.map(lambda t: _generate_one(client, messages, t), temperatures))

    return [r for r in results if r is not None]
