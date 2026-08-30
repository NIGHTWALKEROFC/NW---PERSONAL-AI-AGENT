"""
automation/desktop/vision_verifier.py

Spec section 16's vision capability: before a risky action proceeds,
verify the current screen actually matches what's expected. This uses
a local Ollama vision model (e.g. "moondream" — small, fast, and
genuinely free/local) if one is configured. There is no default vision
model — the main chat model (Qwen2.5 7B) is text-only.

*** Vision model setup is OPTIONAL but affects what you can safely do ***
Without a vision model configured, verification is honestly reported
as "unavailable" — NOT treated as "assume it's fine." The safety
executor treats "unavailable" the same as "does not match" for any
real (non-dry-run) action requiring verification: it stops rather than
guessing. To pull a vision model:

    ollama pull moondream

Then set "vision_model" in config/model_config.json to "moondream".

*** NOT TESTED against a real vision model or real screenshot ***
The HTTP call shape here mirrors agent/brain/model_client.py's
existing pattern (already tested elsewhere in this project), but the
actual image-understanding quality of any given vision model is
something only you can judge on your machine.
"""

import base64
import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

MODEL_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "model_config.json")

VERIFICATION_SYSTEM_PROMPT = """You are shown a screenshot and a description of what the screen is
expected to look like. Determine whether the screenshot matches that expectation closely enough to
proceed safely.

Respond with ONLY a JSON object, no markdown fences, no commentary, in exactly this shape:

{
  "matches_expected": true,
  "description": "one sentence describing what you actually see"
}
"""

DESCRIBE_SYSTEM_PROMPT = """Describe what is visible on this screen in 1-2 sentences: what
application appears open, what the main visible content is, and whether there are any dialogs,
error messages, or login prompts visible. Respond with plain text only, no JSON."""


def _get_configured_vision_model() -> str | None:
    if not os.path.exists(MODEL_CONFIG_PATH):
        return None
    with open(MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("vision_model")


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _call_vision_model(image_path: str, system_prompt: str, user_prompt: str) -> dict:
    vision_model = _get_configured_vision_model()
    if not vision_model:
        return {"available": False, "error": "No vision_model configured in config/model_config.json.", "content": None}

    try:
        image_b64 = _encode_image(image_path)
    except OSError as e:
        return {"available": False, "error": f"Could not read screenshot file: {e}", "content": None}

    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt, "images": [image_b64]},
                ],
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"available": False, "error": f"Vision model call failed: {e}", "content": None}

    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return {"available": True, "error": None, "content": content}


def check_match(image_path: str, expected_description: str) -> dict:
    """
    Returns {"matches_expected": bool, "description": str, "available": bool}.

    "available": False means verification genuinely could not be performed
    (no vision model, or the call failed) — the caller must NOT treat this
    as a pass. "matches_expected" is only meaningful when "available" is True.
    """
    result = _call_vision_model(
        image_path, VERIFICATION_SYSTEM_PROMPT, f"Expected: {expected_description}"
    )

    if not result["available"]:
        return {"matches_expected": False, "description": result["error"], "available": False}

    cleaned = _strip_json_fences(result["content"])
    try:
        parsed = json.loads(cleaned)
        return {
            "matches_expected": bool(parsed.get("matches_expected", False)),
            "description": parsed.get("description", ""),
            "available": True,
        }
    except json.JSONDecodeError:
        return {
            "matches_expected": False,
            "description": f"Vision model did not return valid JSON: {cleaned}",
            "available": True,
        }


def describe_screen(image_path: str) -> dict:
    """Returns {"description": str, "available": bool}."""
    result = _call_vision_model(image_path, DESCRIBE_SYSTEM_PROMPT, "Describe this screen.")
    if not result["available"]:
        return {"description": result["error"], "available": False}
    return {"description": result["content"], "available": True}
