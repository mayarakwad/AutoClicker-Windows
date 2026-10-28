"""'Hotkey setting' dialog: change the global start/stop hotkey."""
import tkinter as tk
from tkinter import ttk

import theme
from hotkeys import DEFAULT_HOTKEY, combo_problem, display_name
from platforms import EXAMPLE_COMBO

HINT = f"Click Change, then press the new key or combination (e.g. F8 or {display_name(EXAMPLE_COMBO)})."


class HotkeyDialog:
    """Modal dialog.

    Keys are captured by the global HotkeyListener (via `listen`), so a
    recorded name is exactly what it will listen for; the App forwards them
    to key_pressed(). `on_close(hotkey)` gets the new hotkey, or None on Cancel.
    """

    def __init__(self, parent, hotkey, listen, stop_listening, on_close):
        self.hotkey = hotkey
        self.recording = False
        self._listen = listen
        self._stop_listening = stop_listening
        self._on_close = on_close

        win = self.window = tk.Toplevel(parent)
        win.title("Hotkey setting")
        win.resizable(False, False)
        win.transient(parent)
        win.protocol("WM_DELETE_WINDOW", self.cancel)
        frame = ttk.Frame(win, padding=12)
        frame.grid()
        ttk.Label(frame, text="Start / Stop").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.key_label = ttk.Label(frame, width=28, anchor="center", relief="sunken", padding=(6, 4))
        self.key_label.grid(row=0, column=1)
        ttk.Button(frame, text="Change", command=self.start_recording).grid(row=0, column=2, padx=(8, 0))
        self.message = ttk.Label(frame, wraplength=380)
        self.message.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text=f"Default ({display_name(DEFAULT_HOTKEY)})",
                   command=self.reset).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="OK", command=self.ok).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(buttons, text="Cancel", command=self.cancel).grid(row=0, column=2)
        self._show(HINT)

        theme.style_window(win)
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        win.geometry(f"+{x}+{parent.winfo_rooty() + 40}")
        win.grab_set()
        win.focus_set()

    def _show(self, message, error=False):
        self.key_label.config(text="Press a key or combination…" if self.recording else display_name(self.hotkey))
        self.message.config(text=message, foreground=theme.color("error") if error else "")

    def start_recording(self):
        self.recording = True
        self._listen()
        self._show("Press Esc to cancel.")

    def cancel_recording(self):
        self.recording = False
        self._stop_listening()
        self._show(HINT)

    def key_pressed(self, combo):
        if not self.recording:
            return
        problem = combo_problem(combo)
        if problem:
            self._listen()  # keep listening for another key
            self._show(f"{display_name(combo)}: {problem}.", error=True)
            return
        self.recording = False
        self.hotkey = combo
        self._show(HINT)

    def reset(self):
        if self.recording:
            self.cancel_recording()
        self.hotkey = DEFAULT_HOTKEY
        self._show(HINT)

    def ok(self):
        self._close(self.hotkey)

    def cancel(self):
        self._close(None)

    def _close(self, hotkey):
        self.recording = False
        self._stop_listening()
        self.window.grab_release()
        self.window.destroy()
        self._on_close(hotkey)
