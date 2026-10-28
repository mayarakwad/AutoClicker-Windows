"""'Personalize' dialog: theme, always on top, opacity and start/stop sounds.

It edits the App's own Tk variables, so every change previews immediately;
Cancel puts the original values back.
"""
import tkinter as tk
from tkinter import ttk

import theme
from platforms import OS_NAME

DEFAULTS = {"theme": "system", "always_on_top": False, "opacity": 100, "sounds": False}
MIN_OPACITY = 40
OPACITY_STEP = 5


class PersonalizeDialog:
    """Modal dialog. `variables` maps the DEFAULTS keys to the App's Tk
    variables; `on_close(saved)` is told whether OK was pressed."""

    def __init__(self, parent, variables, test_sound, on_close):
        self._vars = variables
        self._original = {key: var.get() for key, var in variables.items()}
        self._on_close = on_close

        win = self.window = tk.Toplevel(parent)
        win.title("Personalize")
        win.resizable(False, False)
        win.transient(parent)
        win.protocol("WM_DELETE_WINDOW", self.cancel)
        frame = ttk.Frame(win, padding=12)
        frame.grid()

        ttk.Label(frame, text="Theme").grid(row=0, column=0, sticky="w", padx=(0, 14))
        modes = ttk.Frame(frame)
        modes.grid(row=0, column=1, columnspan=2, sticky="w")
        for i, (value, label) in enumerate((("system", f"Same as {OS_NAME}"), ("light", "Light"), ("dark", "Dark"))):
            ttk.Radiobutton(modes, text=label, value=value,
                            variable=variables["theme"]).grid(row=0, column=i, padx=(0, 14))

        ttk.Label(frame, text="Window").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Checkbutton(frame, text="Always on top",
                        variable=variables["always_on_top"]).grid(row=1, column=1, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Label(frame, text="Opacity").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Scale(frame, from_=MIN_OPACITY, to=100, length=220, variable=variables["opacity"],
                  command=self._snap_opacity).grid(row=2, column=1, sticky="w", pady=(10, 0))
        self.opacity_label = ttk.Label(frame, width=5, anchor="e")
        self.opacity_label.grid(row=2, column=2, sticky="e", pady=(10, 0))

        ttk.Label(frame, text="Sounds").grid(row=3, column=0, sticky="w", pady=(10, 0))
        row = ttk.Frame(frame)
        row.grid(row=3, column=1, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(row, text="Beep when clicking starts and stops",
                        variable=variables["sounds"]).grid(row=0, column=0)
        ttk.Button(row, text="Test", width=6, command=test_sound).grid(row=0, column=1, padx=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Defaults", command=self.defaults).grid(row=0, column=0, sticky="w")
        ttk.Button(buttons, text="OK", command=self.ok).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(buttons, text="Cancel", command=self.cancel).grid(row=0, column=2)
        self._show_opacity()

        theme.style_window(win)
        x = parent.winfo_rootx() + (parent.winfo_width() - win.winfo_width()) // 2
        win.geometry(f"+{x}+{parent.winfo_rooty() + 40}")
        win.grab_set()
        win.focus_set()

    def _snap_opacity(self, value):
        snapped = round(float(value) / OPACITY_STEP) * OPACITY_STEP
        if self._vars["opacity"].get() != snapped:
            self._vars["opacity"].set(snapped)
        self._show_opacity()

    def _show_opacity(self):
        self.opacity_label.config(text=f"{self._vars['opacity'].get()}%")

    def defaults(self):
        for key, value in DEFAULTS.items():
            self._vars[key].set(value)
        self._show_opacity()

    def ok(self):
        self._close(True)

    def cancel(self):
        for key, value in self._original.items():
            if self._vars[key].get() != value:
                self._vars[key].set(value)
        self._close(False)

    def _close(self, saved):
        self.window.grab_release()
        self.window.destroy()
        self._on_close(saved)
