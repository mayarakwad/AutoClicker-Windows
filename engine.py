"""Click engine: runs clicking on a background thread.

Two kinds of run: ClickConfig (repeat one click on an interval) and
PlaybackConfig (replay recorded steps). Contains no UI code. The window
starts and stops the engine and polls `running`, `clicks` and `stop_reason`
to show status. `clicks` counts click actions, so a double click counts once.
"""
import random
import threading
import time
from dataclasses import dataclass

from platforms import Mouse

BUTTONS = ("left", "right", "middle")

# Fail-safe: the cursor within this many pixels of the main screen's
# top-left corner (0, 0) stops clicking.
FAILSAFE_MARGIN = 2

# Longest single sleep, so stop requests and the fail-safe are noticed
# quickly even when the interval is long.
POLL_SECONDS = 0.05

# Shortest interval: 0.1 ms, up to about 10,000 clicks a second.
MIN_INTERVAL_NS = 100_000
MIN_INTERVAL_MS = MIN_INTERVAL_NS / 1_000_000

# Waits shorter than this are timed by watching the clock, because sleep
# can't time anything under about a millisecond. That keeps one CPU core
# busy, but only while clicking this fast.
SPIN_SECONDS = 0.002


@dataclass
class ClickConfig:
    interval_ms: float = 100    # may have a fraction (the window's nanoseconds box), e.g. 1.5
    random_offset_ms: int = 0   # each delay is the interval ± up to this much
    button: str = "left"
    double: bool = False
    repeat: int = 0             # clicks before stopping; 0 = until stopped
    position: tuple = None      # (x, y) to click at; None = wherever the cursor is


@dataclass
class Step:
    delay_ms: int  # wait before this click: since the previous one, or since playback started
    button: str
    x: int
    y: int


@dataclass
class PlaybackConfig:
    steps: list
    loop: bool = False


def next_delay(config):
    """Seconds until the next click, with the random offset applied (never under the minimum)."""
    ms = config.interval_ms
    if config.random_offset_ms:
        ms += random.randint(-config.random_offset_ms, config.random_offset_ms)
    return max(ms, MIN_INTERVAL_MS) / 1000


class ClickEngine:
    def __init__(self, mouse=None):
        self._mouse = mouse or Mouse()
        self._thread = None
        self._stop_event = threading.Event()
        self.clicks = 0
        self.stop_reason = ""

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, config):
        if self.running:
            return
        if isinstance(config, PlaybackConfig):
            if not config.steps:
                raise ValueError("Nothing recorded")
            for step in config.steps:
                if step.delay_ms < 1 or step.button not in BUTTONS:
                    raise ValueError(f"Bad recorded step: {step}")
            target = self._play
        else:
            if config.interval_ms < MIN_INTERVAL_MS:
                raise ValueError(f"Interval must be at least {MIN_INTERVAL_MS:g} ms ({MIN_INTERVAL_NS} nanoseconds)")
            if config.random_offset_ms < 0:
                raise ValueError("Random offset can't be negative")
            if config.repeat < 0:
                raise ValueError("Repeat count can't be negative")
            if config.button not in BUTTONS:
                raise ValueError(f"Unknown mouse button: {config.button!r}")
            target = self._run
        self.clicks = 0
        self.stop_reason = ""
        self._stop_event.clear()
        self._thread = threading.Thread(target=target, args=(config,), daemon=True)
        self._thread.start()

    def stop(self, reason=""):
        """Ask the click thread to stop. `reason` is shown in the status line."""
        if self.running and not self._stop_event.is_set():
            self.stop_reason = reason
        self._stop_event.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self, config):
        button = config.button
        count = 2 if config.double else 1
        delay = next_delay(config)
        next_click = time.perf_counter() + delay
        while self._wait_until(next_click, spin=delay < SPIN_SECONDS):
            if config.position is None:
                self._mouse.click(button, count)
            else:
                self._mouse.click_at(*config.position, button, count)
            self.clicks += 1
            if config.repeat and self.clicks >= config.repeat:
                self.stop_reason = "finished"
                return
            delay = next_delay(config)
            next_click += delay
            now = time.perf_counter()
            if next_click < now:
                # Fell behind (busy system): carry on from now instead of
                # firing a burst of clicks to catch up.
                next_click = now

    def _play(self, playback):
        steps = list(playback.steps)
        next_click = time.perf_counter()
        while True:
            for step in steps:
                delay = step.delay_ms / 1000
                next_click += delay
                if not self._wait_until(next_click, spin=delay < SPIN_SECONDS):
                    return
                self._mouse.click_at(step.x, step.y, step.button)
                self.clicks += 1
                next_click = max(next_click, time.perf_counter())  # no catch-up bursts
            if not playback.loop:
                self.stop_reason = "finished"
                return

    def _wait_until(self, deadline, spin=False):
        """Wait until `deadline`. Returns False if stopped or the fail-safe tripped.

        With `spin`, the last SPIN_SECONDS are timed by watching the clock
        instead of sleeping; stop and the fail-safe are checked just before.
        """
        while True:
            if self._stop_event.is_set():
                return False
            if self._in_failsafe_corner():
                self.stop_reason = "mouse in top-left corner"
                return False
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return True
            if spin and remaining <= SPIN_SECONDS:
                while time.perf_counter() < deadline:
                    time.sleep(0)  # lets the window and hotkey threads run meanwhile
                return True
            # time.sleep uses a high-resolution timer on Windows (Python 3.11+),
            # so short intervals stay accurate even while the window is minimized.
            time.sleep(min(remaining - (SPIN_SECONDS if spin else 0), POLL_SECONDS))

    def _in_failsafe_corner(self):
        x, y = self._mouse.position
        return abs(x) <= FAILSAFE_MARGIN and abs(y) <= FAILSAFE_MARGIN
