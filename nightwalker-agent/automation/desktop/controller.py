"""
automation/desktop/controller.py

*** THESE FUNCTIONS HAVE NOT BEEN TESTED AGAINST A REAL DISPLAY ***
There is no GUI in the environment this was built in — no Windows, no
X server, nothing to click. Every function here is written to the best
of my knowledge of pyautogui's documented API, but none of it has been
run and observed by me. Test each one individually, in isolation, on
something low-stakes (Notepad, a scratch text file) before trusting it
with anything real. Start with scripts/desktop_action_cli.py in
dry-run mode, then move to real execution only once you've watched it
work correctly on something that doesn't matter.

Every function here does the single narrow thing it's named for and
nothing more — safety orchestration (permission checks, verification,
stop-on-failure) lives in safety_executor.py, not here.
"""

import subprocess
import sys


def open_application(name_or_path: str) -> dict:
    """
    Opens an application by name (if it's on PATH) or a full path.
    On Windows, os.startfile is the standard, simplest way to do this —
    it defers to the OS's own file/app association logic, same as
    double-clicking it yourself.
    """
    try:
        if sys.platform == "win32":
            import os
            os.startfile(name_or_path)
        else:
            subprocess.Popen([name_or_path])
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def click(x: int, y: int) -> dict:
    try:
        import pyautogui
        pyautogui.click(x, y)
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def type_text(text: str, interval: float = 0.02) -> dict:
    """interval: seconds between keystrokes — a small delay reads more naturally
    than instant paste and is gentler on whatever app receives the input."""
    try:
        import pyautogui
        pyautogui.write(text, interval=interval)
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {e}"}


def list_open_windows() -> dict:
    try:
        import pygetwindow as gw
        titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
        return {"success": True, "windows": titles, "error": None}
    except Exception as e:
        return {"success": False, "windows": [], "error": f"{type(e).__name__}: {e}"}
