"""
automation/desktop/recorder.py

Captures a manual demonstration ("TEACH ME") session for Phase 12:
mouse clicks and keyboard input, recorded to memory only, for
scripts/teach_me_cli.py to hand off to workflow_builder.py afterward.

*** NOT TESTED against a real display/input devices ***
pynput is imported LAZILY, exactly like pyautogui/pygetwindow
elsewhere in this package (see availability.py) — confirmed here too,
the same way: importing pynput.mouse/pynput.keyboard at module load
time crashes immediately in this headless Linux sandbox with
"ImportError: this platform is not supported ... failed to acquire X
connection". A top-level import would have broken this whole module
just from being imported, on any machine without a working display
connection — including, conceivably, a remote/headless session on the
real Windows machine. So exactly like Phase 11, nothing pynput-related
is imported until a recording is actually started (see start() below).

What HAS been tested in this sandbox: the pynput import crash above,
and all of the pure event-handling logic below (_on_click,
_on_key_press, text coalescing, the max-duration cap) by calling those
methods directly with synthetic events, bypassing the real
pynput.mouse.Listener / pynput.keyboard.Listener objects — because
there is no real mouse or keyboard here to generate real events with.

*** Never logs to disk on its own ***
Everything captured during a recording lives in memory in the Recorder
instance only, for the duration of that recording. Nothing here writes
to database/nightwalker.db or any file — that only happens if/when the
caller (teach_me_cli.py, after the user has reviewed and possibly
redacted the captured steps) explicitly calls
database/workflow_store.py to save it. Stopping a recording without
saving it simply discards it once the object is garbage collected.

*** Hard duration cap, enforced by wall-clock, not just by activity ***
MAX_RECORDING_SECONDS bounds every recording via a background timer
that calls stop() regardless of whether any events are still coming
in — a recording that's still running because of a forgotten terminal,
a crashed caller, or a genuine mistake should not be able to capture
indefinitely just because nothing happened to trip an event-driven
check.
"""

import threading
import time

MAX_RECORDING_SECONDS = 600  # 10 minutes — a demonstration is meant to be a short, focused walkthrough


class Recorder:
    """
    One recording session's captured raw events, in memory only.

    Raw event shape (each a dict appended to self.events, in order):
        {"type": "click", "x": int, "y": int, "button": str, "t": float}
        {"type": "key", "text": str, "t": float}
            # printable characters, coalesced into runs — see _flush_text_buffer
        {"type": "key_special", "name": str, "t": float}
            # a non-printable key (e.g. "Key.enter", "Key.tab") in pynput's own str() form

    "t" is seconds since recording start, kept for human review context
    only — workflow_builder.py does not currently use timing to drive
    replay speed.
    """

    def __init__(self, max_seconds: int = MAX_RECORDING_SECONDS):
        self.events: list[dict] = []
        self.max_seconds = max_seconds
        self._start_time: float | None = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._watchdog: threading.Timer | None = None
        self._text_buffer = ""
        self._stopped = False

    def _elapsed(self) -> float:
        return time.monotonic() - self._start_time if self._start_time else 0.0

    def _flush_text_buffer(self):
        if self._text_buffer:
            self.events.append({"type": "key", "text": self._text_buffer, "t": self._elapsed()})
            self._text_buffer = ""

    def _on_click(self, x, y, button, pressed):
        """pynput's on_click callback signature: (x, y, button, pressed). Only the press
        (pressed=True) is recorded — a click is captured once, not once per press+release."""
        if not pressed or self._stopped:
            return
        self._flush_text_buffer()
        self.events.append({"type": "click", "x": int(x), "y": int(y), "button": str(button), "t": self._elapsed()})

    def _on_key_press(self, key):
        """pynput's on_press callback. Returning False stops the listener; returning
        anything else (including None) keeps it running."""
        if self._stopped:
            return False
        try:
            char = key.char
        except AttributeError:
            char = None

        if char is not None:
            self._text_buffer += char
        else:
            self._flush_text_buffer()
            self.events.append({"type": "key_special", "name": str(key), "t": self._elapsed()})
        return None

    def start(self):
        """
        Raises whatever pynput raises if it can't attach listeners (e.g. no display) —
        the caller (teach_me_cli.py) is responsible for catching this and reporting it
        clearly, same pattern as availability.check_all() elsewhere in this package.
        """
        from pynput import mouse, keyboard  # lazy import — see module docstring

        self._start_time = time.monotonic()
        self._stopped = False
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self._mouse_listener.start()
        self._keyboard_listener.start()

        self._watchdog = threading.Timer(self.max_seconds, self.stop)
        self._watchdog.daemon = True
        self._watchdog.start()

    def stop(self) -> list[dict]:
        """Stops listening and returns the captured events. Safe to call more than once."""
        self._stopped = True
        self._flush_text_buffer()
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
        if self._watchdog is not None:
            self._watchdog.cancel()
        return self.events
