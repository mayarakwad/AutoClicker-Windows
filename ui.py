"""Main window (tkinter). Drives the click engine; contains no clicking logic."""
import queue
import re
import tkinter as tk
from tkinter import ttk

import platforms
import settings
import theme
from engine import MIN_INTERVAL_MS, MIN_INTERVAL_NS, ClickConfig, ClickEngine
from hotkey_dialog import HotkeyDialog
from hotkeys import DEFAULT_HOTKEY, HotkeyListener, combo_problem, display_name
from platforms import PointPicker, on_screen
from personalize_dialog import DEFAULTS as LOOK_DEFAULTS, MIN_OPACITY, PersonalizeDialog
from recorder import dump_steps, load_steps
from recorder_window import RecorderWindow

# How often the window checks hotkey events and engine status.
POLL_MS = 50
# How often (in polls) a "Same as Windows/macOS" theme checks for an OS change,
# and macOS re-checks its Accessibility/Input Monitoring permissions.
SYSTEM_THEME_POLLS = 40
# How often the pick tooltip follows the cursor.
TIP_MS = 30

BUTTON_NAMES = ["Left", "Right", "Middle"]
CLICK_TYPES = ["Single", "Double"]


def _is_digits(text):
    """Entry validator: allow only empty text or up to 9 ASCII digits."""
    return text == "" or (len(text) <= 9 and text.isascii() and text.isdigit())


def _is_coordinate(text):
    """Entry validator for X/Y: digits with an optional leading minus.

    Screens left of or above the main one have negative coordinates.
    """
    return len(text) <= 7 and _is_digits(text.removeprefix("-"))


def _set_enabled(widget, enabled):
    widget.state(["!disabled" if enabled else "disabled"])


class App:
    def __init__(self, root, settings_path=None):
        self.root = root
        self.settings_path = settings_path
        self.engine = ClickEngine()
        self.error = ""
        self.picker = None
        self.tip = None
        self.dialog = None
        self.recorder_window = None
        self.personalize = None
        self.notice = ""  # macOS only: missing Accessibility/Input Monitoring permission
        self.was_running = False
        self.polls = 0
        self.window_pos = None
        # Personalization; the Personalize dialog edits these directly.
        self.theme_mode = tk.StringVar(value=LOOK_DEFAULTS["theme"])
        self.always_on_top = tk.BooleanVar(value=LOOK_DEFAULTS["always_on_top"])
        self.opacity = tk.IntVar(value=LOOK_DEFAULTS["opacity"])
        self.sounds = tk.BooleanVar(value=LOOK_DEFAULTS["sounds"])
        saved = settings.load(settings_path)
        hotkey = saved.get("hotkey")
        if not isinstance(hotkey, str) or combo_problem(hotkey):
            hotkey = DEFAULT_HOTKEY
        self.steps = load_steps(saved.get("recording"))
        self.playback_loop = saved.get("playback_loop") is True
        # Hotkeys and the picker fire on pynput's threads; queue their events
        # as tuples so tkinter is only touched from the main thread.
        self.events = queue.Queue()
        self.hotkeys = HotkeyListener(
            on_toggle=lambda: self.events.put(("toggle",)),
            on_escape=lambda: self.events.put(("escape",)),
            hotkey=hotkey,
        )
        self._build()
        self._apply_settings(saved)
        self._restore_position(saved)
        self._follow_look()
        self.notice = platforms.permission_problem() or ""
        if self.notice:
            platforms.request_permissions()
        self.hotkeys.start()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll()

    def _build(self):
        root = self.root
        root.title("AutoClicker")
        root.resizable(False, False)

        outer = ttk.Frame(root, padding=10)
        outer.grid()
        outer.columnconfigure((0, 1), weight=1, uniform="half")
        digits = (root.register(_is_digits), "%P")
        coordinate = (root.register(_is_coordinate), "%P")

        def number_entry(parent, var, validate=digits, width=6):
            return ttk.Entry(parent, textvariable=var, width=width, justify="right",
                             validate="key", validatecommand=validate)

        box = ttk.LabelFrame(outer, text="Click interval", padding=(10, 6))
        box.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.hours = tk.StringVar(value="0")
        self.mins = tk.StringVar(value="0")
        self.secs = tk.StringVar(value="0")
        self.millis = tk.StringVar(value="100")
        self.nanos = tk.StringVar(value="0")
        fields = ((self.hours, "hours"), (self.mins, "mins"), (self.secs, "secs"),
                  (self.millis, "milliseconds"), (self.nanos, "nanoseconds"))
        for i, (var, label) in enumerate(fields):
            width = 10 if var is self.nanos else 6  # up to 999999999
            number_entry(box, var, width=width).grid(row=0, column=i * 2, padx=(0 if i == 0 else 10, 4))
            ttk.Label(box, text=label).grid(row=0, column=i * 2 + 1, sticky="w")
        row = ttk.Frame(box)
        row.grid(row=1, column=0, columnspan=10, sticky="w", pady=(6, 0))
        self.use_offset = tk.BooleanVar(value=False)
        self.offset = tk.StringVar(value="40")
        ttk.Checkbutton(row, text="Random offset ±", variable=self.use_offset).grid(row=0, column=0)
        self.offset_entry = number_entry(row, self.offset)
        self.offset_entry.grid(row=0, column=1, padx=4)
        ttk.Label(row, text="milliseconds").grid(row=0, column=2)

        box = ttk.LabelFrame(outer, text="Click options", padding=(10, 6))
        box.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=(8, 0))
        self.button = tk.StringVar(value="Left")
        self.click_type = tk.StringVar(value="Single")
        combos = (("Mouse button:", self.button, BUTTON_NAMES), ("Click type:", self.click_type, CLICK_TYPES))
        for i, (label, var, values) in enumerate(combos):
            ttk.Label(box, text=label).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Combobox(box, textvariable=var, values=values, state="readonly",
                         width=8).grid(row=i, column=1, padx=(8, 0), pady=2)

        box = ttk.LabelFrame(outer, text="Click repeat", padding=(10, 6))
        box.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(8, 0))
        self.repeat_mode = tk.StringVar(value="forever")
        self.repeat_count = tk.StringVar(value="1")
        ttk.Radiobutton(box, text="Repeat", value="count",
                        variable=self.repeat_mode).grid(row=0, column=0, sticky="w", pady=2)
        self.repeat_entry = number_entry(box, self.repeat_count)
        self.repeat_entry.grid(row=0, column=1, padx=4)
        ttk.Label(box, text="times").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(box, text="Repeat until stopped", value="forever",
                        variable=self.repeat_mode).grid(row=1, column=0, columnspan=3, sticky="w", pady=2)

        box = ttk.LabelFrame(outer, text="Cursor position", padding=(10, 6))
        box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.position_mode = tk.StringVar(value="current")
        self.x = tk.StringVar(value="0")
        self.y = tk.StringVar(value="0")
        ttk.Radiobutton(box, text="Current location", value="current",
                        variable=self.position_mode).grid(row=0, column=0, padx=(0, 16))
        ttk.Radiobutton(box, value="pick", variable=self.position_mode).grid(row=0, column=1)
        self.pick_button = ttk.Button(box, text="Pick location", command=self.pick_location)
        self.pick_button.grid(row=0, column=2, padx=(0, 10))
        ttk.Label(box, text="X").grid(row=0, column=3)
        self.x_entry = number_entry(box, self.x, coordinate)
        self.x_entry.grid(row=0, column=4, padx=(4, 10))
        ttk.Label(box, text="Y").grid(row=0, column=5)
        self.y_entry = number_entry(box, self.y, coordinate)
        self.y_entry.grid(row=0, column=6, padx=(4, 0))

        self.start_button = ttk.Button(outer, command=self.start)
        self.start_button.grid(row=3, column=0, sticky="ew", padx=(0, 4), pady=(10, 0), ipady=6)
        self.stop_button = ttk.Button(outer, command=self.stop)
        self.stop_button.grid(row=3, column=1, sticky="ew", padx=(4, 0), pady=(10, 0), ipady=6)
        tools = ttk.Frame(outer)
        tools.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        tools.columnconfigure((0, 1, 2), weight=1, uniform="tool")
        self.hotkey_button = ttk.Button(tools, text="Hotkey setting", command=self.open_hotkey_dialog)
        self.recorder_button = ttk.Button(tools, text="Record & Playback", command=self.open_recorder)
        self.personalize_button = ttk.Button(tools, text="Personalize", command=self.open_personalize)
        for i, button in enumerate((self.hotkey_button, self.recorder_button, self.personalize_button)):
            button.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
        self._update_hotkey_labels()

        self.status = ttk.Label(outer, anchor="w")
        self.status.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        outer.update_idletasks()  # wrap long messages instead of widening the window
        self.status.config(wraplength=outer.winfo_reqwidth() - 20)
        # Traces (not widget commands) so entries also follow values set in code.
        for var in (self.use_offset, self.repeat_mode, self.position_mode):
            var.trace_add("write", lambda *_: self._sync_inputs())
        self._sync_inputs()
        self._refresh()

    def _update_hotkey_labels(self):
        key = display_name(self.hotkeys.hotkey)
        self.start_button.config(text=f"Start ({key})")
        self.stop_button.config(text=f"Stop ({key})")

    def _setting_vars(self):
        """Settings key -> (variable, check that a loaded value is usable)."""
        def digits(v):
            return isinstance(v, str) and _is_digits(v)

        def coordinate(v):
            return isinstance(v, str) and _is_coordinate(v)

        def one_of(*options):
            return lambda v: isinstance(v, str) and v in options

        def flag(v):
            return isinstance(v, bool)

        return {
            "hours": (self.hours, digits),
            "mins": (self.mins, digits),
            "secs": (self.secs, digits),
            "millis": (self.millis, digits),
            "nanos": (self.nanos, digits),
            "use_offset": (self.use_offset, flag),
            "offset": (self.offset, digits),
            "button": (self.button, one_of(*BUTTON_NAMES)),
            "click_type": (self.click_type, one_of(*CLICK_TYPES)),
            "repeat_mode": (self.repeat_mode, one_of("count", "forever")),
            "repeat_count": (self.repeat_count, digits),
            "position_mode": (self.position_mode, one_of("current", "pick")),
            "x": (self.x, coordinate),
            "y": (self.y, coordinate),
            "theme": (self.theme_mode, one_of(*theme.MODES)),
            "always_on_top": (self.always_on_top, flag),
            "opacity": (self.opacity, lambda v: type(v) is int and MIN_OPACITY <= v <= 100),
            "sounds": (self.sounds, flag),
        }

    def _apply_settings(self, saved):
        """Restore saved values; anything missing or invalid keeps its default."""
        for key, (var, usable) in self._setting_vars().items():
            if key in saved and usable(saved[key]):
                var.set(saved[key])

    def _restore_position(self, saved):
        """Reopen where the window was last, if that spot is still on a screen."""
        x, y = saved.get("window_x"), saved.get("window_y")
        if type(x) is int and type(y) is int and on_screen(x + 40, y + 15):  # a point in the title bar
            self.window_pos = (x, y)
            self.root.geometry(f"+{x}+{y}")

    def _follow_look(self):
        """Apply theme, always-on-top and opacity now, and again whenever they change."""
        actions = (
            (self.theme_mode, lambda: theme.apply(self.root, self.theme_mode.get())),
            (self.always_on_top, lambda: self.root.attributes("-topmost", self.always_on_top.get())),
            (self.opacity, lambda: self.root.attributes("-alpha", self.opacity.get() / 100)),
        )
        for var, action in actions:
            action()
            var.trace_add("write", lambda *_, action=action: action())

    def _save_settings(self):
        data = {key: var.get() for key, (var, _) in self._setting_vars().items()}
        data["hotkey"] = self.hotkeys.hotkey
        data["recording"] = dump_steps(self.steps)
        data["playback_loop"] = self.playback_loop
        # Minimized or hidden windows report bogus positions; keep the last real one.
        if self.root.state() == "normal":
            match = re.search(r"\+(-?\d+)\+(-?\d+)$", self.root.geometry())
            if match:
                self.window_pos = (int(match[1]), int(match[2]))
        if self.window_pos is not None:
            data["window_x"], data["window_y"] = self.window_pos
        try:
            settings.save(data, self.settings_path)
        except OSError:
            pass  # not worth interrupting clicking over; defaults return next launch

    def _sync_inputs(self):
        """Enable each entry only while the option it belongs to is selected."""
        _set_enabled(self.offset_entry, self.use_offset.get())
        _set_enabled(self.repeat_entry, self.repeat_mode.get() == "count")
        picked = self.position_mode.get() == "pick"
        _set_enabled(self.x_entry, picked)
        _set_enabled(self.y_entry, picked)

    @staticmethod
    def _number(var, name):
        text = var.get().strip()
        if not text:
            raise ValueError(f"{name} can't be empty")
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"{name} must be a number") from None

    def _read_config(self):
        """Build a ClickConfig from the inputs; ValueError carries the message to show."""
        # Whole nanoseconds, so the minimum check is exact.
        interval_ns = ((self._number(self.hours, "Hours") * 3600
                        + self._number(self.mins, "Mins") * 60
                        + self._number(self.secs, "Secs")) * 1_000_000_000
                       + self._number(self.millis, "Milliseconds") * 1_000_000
                       + self._number(self.nanos, "Nanoseconds"))
        if interval_ns < MIN_INTERVAL_NS:
            raise ValueError(f"Interval must be at least {MIN_INTERVAL_MS:g} ms ({MIN_INTERVAL_NS} nanoseconds)")
        interval = interval_ns / 1_000_000
        offset = self._number(self.offset, "Random offset") if self.use_offset.get() else 0
        repeat = 0
        if self.repeat_mode.get() == "count":
            repeat = self._number(self.repeat_count, "Repeat count")
            if repeat < 1:
                raise ValueError("Repeat count must be at least 1")
        position = None
        if self.position_mode.get() == "pick":
            position = (self._number(self.x, "X"), self._number(self.y, "Y"))
            if not on_screen(*position):
                raise ValueError(f"Location {position[0]}, {position[1]} is not on any screen")
        return ClickConfig(interval_ms=interval, random_offset_ms=offset,
                           button=self.button.get().lower(), double=self.click_type.get() == "Double",
                           repeat=repeat, position=position)

    def start(self):
        if self.engine.running or self.picker is not None:
            return
        self._save_settings()
        self.notice = platforms.permission_problem() or ""
        if self.notice:
            self.root.bell()  # clicks would be silently dropped
            self._refresh()
            return
        try:
            self.engine.start(self._read_config())
        except ValueError as e:
            self.error = str(e)
            self.root.bell()
        else:
            self.error = ""
        self._refresh()

    def stop(self, reason=""):
        self.engine.stop(reason)
        self.error = ""
        self._refresh()

    def toggle(self):
        if self.engine.running:
            self.stop()
        else:
            self.start()

    def pick_location(self):
        """Hide the window; the next left click anywhere sets X/Y (Esc cancels)."""
        if self.engine.running or self.picker is not None:
            return
        self.picker = PointPicker(on_pick=lambda x, y: self.events.put(("picked", x, y)))
        self.picker.start()
        self.root.withdraw()
        self.tip = tk.Toplevel(self.root)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip_label = tk.Label(self.tip, background=theme.color("tip_bg"), foreground=theme.color("tip_fg"),
                                  relief="solid", borderwidth=1, padx=6, pady=3, justify="left")
        self.tip_label.pack()
        self._follow_cursor()

    def _follow_cursor(self):
        if self.tip is None:
            return
        x, y = self.root.winfo_pointerxy()
        self.tip_label.config(text=f"X {x}   Y {y}\nClick to pick this point · Esc to cancel")
        self.tip.geometry(f"+{x + 16}+{y + 20}")
        self._tip_job = self.root.after(TIP_MS, self._follow_cursor)

    def _end_pick(self, point=None):
        self.picker.stop()
        self.picker = None
        self.root.after_cancel(self._tip_job)
        self.tip.destroy()
        self.tip = None
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if point is not None:
            self.x.set(str(point[0]))
            self.y.set(str(point[1]))
            self.position_mode.set("pick")

    def open_hotkey_dialog(self):
        if self.engine.running or self.dialog is not None:
            return
        self.dialog = HotkeyDialog(
            self.root, self.hotkeys.hotkey,
            listen=lambda: self.hotkeys.record(lambda combo: self.events.put(("recorded", combo))),
            stop_listening=self.hotkeys.stop_recording,
            on_close=self._hotkey_dialog_closed,
        )

    def _hotkey_dialog_closed(self, hotkey):
        self.dialog = None
        if hotkey is not None:
            self.hotkeys.hotkey = hotkey
            self._update_hotkey_labels()
            self._save_settings()

    def open_recorder(self):
        if self.engine.running or self.recorder_window is not None:
            return
        self.recorder_window = RecorderWindow(
            self.root, self.engine, self.steps, self.playback_loop,
            hotkey=display_name(self.hotkeys.hotkey), post=self.events.put,
            on_close=self._recorder_closed,
        )

    def _recorder_closed(self, steps, loop):
        self.recorder_window = None
        self.steps = steps
        self.playback_loop = loop
        self._save_settings()

    def open_personalize(self):
        if self.personalize is not None:
            return
        self.personalize = PersonalizeDialog(
            self.root,
            {"theme": self.theme_mode, "always_on_top": self.always_on_top,
             "opacity": self.opacity, "sounds": self.sounds},
            test_sound=lambda: platforms.play_sound(started=True),
            on_close=self._personalize_closed,
        )

    def _personalize_closed(self, saved):
        self.personalize = None
        if saved:
            self._save_settings()

    def close(self):
        if self.personalize is not None:
            self.personalize.cancel()
        if self.recorder_window is not None:
            self.recorder_window.close()
        if self.picker is not None:
            self._end_pick()
        self.engine.stop()
        self.hotkeys.stop()
        self._save_settings()
        self.root.after_cancel(self._poll_job)
        self.root.destroy()

    def _poll(self):
        while True:
            try:
                kind, *args = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "escape":
                # The fail-safe comes first (it also stops playback); Esc also
                # cancels a pick, a hotkey recording or a click recording.
                if self.engine.running:
                    self.stop("Esc pressed")
                if self.picker is not None:
                    self._end_pick()
                if self.dialog is not None and self.dialog.recording:
                    self.dialog.cancel_recording()
                if self.recorder_window is not None and self.recorder_window.recording:
                    self.recorder_window.stop_recording()
            elif kind == "picked" and self.picker is not None:
                self._end_pick(args)
            elif kind == "recorded" and self.dialog is not None:
                self.dialog.key_pressed(args[0])
            elif kind == "step" and self.recorder_window is not None:
                self.recorder_window.add_step(args[0])
            elif kind == "toggle" and self.recorder_window is not None:
                self.recorder_window.toggle()
            elif kind == "toggle" and self.picker is None:
                self.toggle()
        if self.recorder_window is not None:
            self.recorder_window.refresh()
        self.polls += 1
        if self.polls % SYSTEM_THEME_POLLS == 0:
            if self.theme_mode.get() == "system" and theme.resolve("system") != theme.current:
                theme.apply(self.root, "system")  # the OS switched light/dark
            self.notice = platforms.permission_problem() or ""
        self._refresh()
        self._poll_job = self.root.after(POLL_MS, self._poll)

    def _refresh(self):
        running = self.engine.running
        if running != self.was_running:
            # Every start and stop passes through here: buttons, hotkey, Esc,
            # fail-safe, repeat finished, playback.
            self.was_running = running
            platforms.set_clicking(running)
            if self.sounds.get():
                platforms.play_sound(started=running)
        self.start_button.state(["disabled" if running else "!disabled"])
        self.stop_button.state(["!disabled" if running else "disabled"])
        _set_enabled(self.pick_button, not running)
        _set_enabled(self.hotkey_button, not running)
        _set_enabled(self.recorder_button, not running)
        if (self.error or self.notice) and not running:
            self.status.config(text=self.error or self.notice, foreground=theme.color("error"))
            return
        n = self.engine.clicks
        clicks = f"{n:,} click" + ("" if n == 1 else "s")
        if running:
            self.status.config(text=f"Running · {clicks}", foreground=theme.color("running"))
        elif self.engine.stop_reason:
            self.status.config(text=f"Stopped ({self.engine.stop_reason}) · {clicks}", foreground="")
        else:
            self.status.config(text=f"Stopped · {clicks}", foreground="")
