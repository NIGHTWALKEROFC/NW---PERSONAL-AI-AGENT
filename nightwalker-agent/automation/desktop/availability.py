"""
automation/desktop/availability.py

*** IMPORTANT, READ BEFORE TRUSTING ANYTHING IN automation/desktop/ ***

pyautogui and pygetwindow are imported LAZILY (inside functions, never
at module top-level) everywhere in this package. This is not a style
preference — it was discovered empirically while building this: on a
headless Linux environment, `import pyautogui` crashes immediately
with `KeyError('DISPLAY')` because it tries to connect to a display
server the moment it's imported. pygetwindow raises `NotImplementedError`
immediately on Linux, unconditionally. A top-level import would have
crashed this entire module just from being imported, anywhere, for any
reason — including on your real Windows machine if something else
about the environment isn't quite right.

This module exists to check, safely, whether the automation libraries
are actually usable right now, without ever risking a crash just from
checking.

*** WHAT HAS AND HAS NOT BEEN TESTED ***
This availability-checking logic HAS been tested (in a headless Linux
sandbox with no display — confirmed it correctly reports "unavailable"
with a clear reason instead of crashing).

The actual screenshot/click/type/window functions elsewhere in this
package have NOT been tested against a real Windows display — there is
no GUI in the environment this was built in. Test them yourself,
starting with dry-run mode, on something low-stakes (Notepad, a text
editor) before trusting them with anything that matters.
"""


def check_pyautogui() -> dict:
    """Returns {"available": bool, "error": str | None}."""
    try:
        import pyautogui  # noqa: F401 — intentionally imported only to test availability
        return {"available": True, "error": None}
    except Exception as e:
        return {"available": False, "error": f"{type(e).__name__}: {e}"}


def check_pygetwindow() -> dict:
    """Returns {"available": bool, "error": str | None}."""
    try:
        import pygetwindow  # noqa: F401
        return {"available": True, "error": None}
    except Exception as e:
        return {"available": False, "error": f"{type(e).__name__}: {e}"}


def check_all() -> dict:
    pyautogui_status = check_pyautogui()
    pygetwindow_status = check_pygetwindow()
    return {
        "pyautogui": pyautogui_status,
        "pygetwindow": pygetwindow_status,
        "fully_available": pyautogui_status["available"] and pygetwindow_status["available"],
    }
