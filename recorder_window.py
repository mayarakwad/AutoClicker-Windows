"""'Record & Playback' window: record clicks anywhere, then play them back once or on a loop."""
import tkinter as tk
from tkinter import ttk

import theme
from engine import PlaybackConfig
from platforms import on_screen
from recorder import ClickRecorder


def _set_enabled(widget, enabled):
    widget.state(["!disabled" if enabled else "disabled"])


def _plural(n, word):
    return f"{n:,} {word}" + ("" if n == 1 else "s")


class RecorderWindow:
    """Modal window. Playback runs on the App's engine.

    The App routes the start/stop hotkey to toggle(), Esc to stop_recording(),
    recorded clicks to add_step(), and calls refresh() on every poll.
    `on_close(steps, loop)` hands back the recording to save.
    """

    def __init__(self, parent, engine, steps, loop, hotkey, post, on_close):
        self.engine = engine
        self.steps = list(steps)
        self.hotkey = hotkey
        self.recorder = None
        self.played = False
        self.error = ""
        self._post = post
        self._on_close = on_close

        win = self.window = tk.Toplevel(parent)
        win.title("Record & Playback")
        win.resizable(False, False)
        win.transient(parent)
        win.protocol("WM_DELETE_WINDOW", self.close)
        frame = ttk.Frame(win, padding=10)
        frame.grid()

        bar = ttk.Frame(frame)
        bar.grid(row=0, column=0, sticky="w")
        self.record_button = ttk.Button(bar, text="Record", command=self.start_recording)
        self.play_button = ttk.Button(bar, text=f"Play ({hotkey})", command=self.play)
        self.stop_button = ttk.Button(bar, text=f"Stop ({hotkey})", command=self.stop)
        self.clear_button = ttk.Button(bar, text="Clear", command=self.clear)
        for i, button in enumerate((self.record_button, self.play_button, self.stop_button, self.clear_button)):
            button.grid(row=0, column=i, padx=(0 if i == 0 else 6, 0))

        table = ttk.Frame(frame)
        table.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        columns = (("n", "#", 44), ("button", "Button", 80), ("x", "X", 70), ("y", "Y", 70), ("delay", "Delay (ms)", 100))
        # The highlighted row is the step about to play; users don't select rows.
        self.tree = ttk.Treeview(table, columns=[c[0] for c in columns], show="headings",
                                 height=10, selectmode="none")
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, stretch=False, anchor="w" if key == "button" else "e")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0)
        scroll.grid(row=0, column=1, sticky="ns")

        options = ttk.Frame(frame)
        options.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.loop = tk.BooleanVar(value=loop)
        ttk.Label(options, text="Playback:").grid(row=0, column=0, padx=(0, 8))
        ttk.Radiobutton(options, text="Once", value=0, variable=self.loop).grid(row=0, column=1, padx=(0, 12))
        ttk.Radiobutton(options, text="Loop until stopped", value=1, variable=self.loop).grid(row=0, column=2)

        self.status = ttk.Label(frame, anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        for step in self.steps:
            self._insert(step)
        self.refresh()

        theme.style_window(win)
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        win.geometry(f"+{x}+{parent.winfo_rooty() + 20}")
        win.grab_set()
        win.focus_set()

    @property
    def recording(self):
        return self.recorder is not None

    @property
    def busy(self):
        return self.recording or self.engine.running

    def start_recording(self):
        if self.busy:
            return
        self.clear()
        self.recorder = ClickRecorder(on_step=lambda step: self._post(("step", step)))
        self.recorder.start()
        # Stay visible over the apps being clicked, so Stop is reachable
        # without clicking the taskbar (which would be recorded).
        self.window.attributes("-topmost", True)
        self.refresh()

    def stop_recording(self):
        if self.recorder is not None:
            self.recorder.stop()
            self.recorder = None
            self.window.attributes("-topmost", False)
        self.refresh()

    def add_step(self, step):
        if not self.recording:
            return
        self.steps.append(step)
        self.tree.see(self._insert(step))

    def _insert(self, step):
        n = len(self.tree.get_children())
        return self.tree.insert("", "end", iid=str(n),
                                values=(n + 1, step.button.title(), step.x, step.y, f"{step.delay_ms:,}"))

    def play(self):
        if self.busy or not self.steps:
            return
        off = next((i for i, s in enumerate(self.steps) if not on_screen(s.x, s.y)), None)
        if off is not None:
            step = self.steps[off]
            self.error = f"Step {off + 1} ({step.x}, {step.y}) is not on any screen"
            self.window.bell()
        else:
            self.error = ""
            self.played = True
            self.engine.start(PlaybackConfig(self.steps, loop=self.loop.get()))
        self.refresh()

    def stop(self):
        if self.recording:
            self.stop_recording()
        elif self.engine.running:
            self.engine.stop()
        self.refresh()

    def toggle(self):
        if self.busy:
            self.stop()
        else:
            self.play()

    def clear(self):
        if self.busy:
            return
        self.steps = []
        self.played = False
        self.error = ""
        self.tree.delete(*self.tree.get_children())
        self.refresh()

    def close(self):
        self.stop()
        self.window.grab_release()
        self.window.destroy()
        self._on_close(self.steps, self.loop.get())

    def refresh(self):
        playing = self.engine.running
        _set_enabled(self.record_button, not self.busy)
        _set_enabled(self.play_button, not self.busy and bool(self.steps))
        _set_enabled(self.stop_button, self.busy)
        _set_enabled(self.clear_button, not self.busy and bool(self.steps))

        n = len(self.steps)
        if self.recording:
            text, color = f"Recording · {_plural(n, 'click')} · {self.hotkey} or Esc to stop", theme.color("recording")
        elif playing:
            done = self.engine.clicks
            text = f"Playing step {done % n + 1} of {n}"
            if self.loop.get():
                text += f" · loop {done // n + 1}"
            color = theme.color("running")
        elif self.error:
            text, color = self.error, theme.color("error")
        elif self.played and self.engine.stop_reason:
            text, color = f"Stopped ({self.engine.stop_reason}) · {_plural(self.engine.clicks, 'click')} played", ""
        elif n:
            text, color = f"{_plural(n, 'click')} recorded · {self.hotkey} or Play to play back", ""
        else:
            text, color = "Click Record, then click anywhere on screen.", ""
        self.status.config(text=text, foreground=color)

        current = (str(self.engine.clicks % n),) if playing else ()
        if self.tree.selection() != current:
            self.tree.selection_set(current)
            if current:
                self.tree.see(current[0])
