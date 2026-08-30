"""
automation/desktop/screen_capture.py

*** NOT TESTED against a real display — see availability.py's docstring. ***

Captures a screenshot for the safety layer to verify against before a
real action proceeds. If capture fails for any reason (no display, no
permission, pyautogui not installed), this returns a clear failure
rather than raising — the caller (safety_executor.py) is responsible
for treating "capture unavailable" as "cannot verify, so stop" for any
real (non-dry-run) risky action.

Screenshots are saved to a temporary, gitignored folder and are NOT
persisted long-term or added to the encrypted database — a screenshot
could contain far more sensitive on-screen content than this project's
existing encryption model was designed around, so the simplest safe
choice is: don't keep them around at all longer than needed.
"""

import os
import datetime

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "database", "_screenshots_tmp")
MAX_RETAINED_SCREENSHOTS = 5  # keep only the most recent few, for debugging a failure — never a long-term log


def _cleanup_old_screenshots():
    if not os.path.exists(SCREENSHOT_DIR):
        return
    files = sorted(
        (os.path.join(SCREENSHOT_DIR, f) for f in os.listdir(SCREENSHOT_DIR)),
        key=os.path.getmtime,
    )
    for old_file in files[:-MAX_RETAINED_SCREENSHOTS] if len(files) > MAX_RETAINED_SCREENSHOTS else []:
        try:
            os.remove(old_file)
        except OSError:
            pass


def capture_screenshot() -> dict:
    """Returns {"available": bool, "path": str | None, "error": str | None}."""
    try:
        import pyautogui
    except Exception as e:
        return {"available": False, "path": None, "error": f"pyautogui unavailable: {type(e).__name__}: {e}"}

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    _cleanup_old_screenshots()

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(SCREENSHOT_DIR, f"screen_{timestamp}.png")

    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(path)
        return {"available": True, "path": path, "error": None}
    except Exception as e:
        return {"available": False, "path": None, "error": f"Screenshot capture failed: {type(e).__name__}: {e}"}
