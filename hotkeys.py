"""Global start/stop hotkey and Esc, on top of the OS's key source.

Keys have OS-independent names ('f6', 'a', 'page_up'); platforms.KeySource
turns each OS's key codes into them. A hotkey is a combo string: modifiers in
a fixed order, then the key ('ctrl+shift+f6'). 'win' is the Windows key on
Windows and Command on macOS.
"""
import platforms

DEFAULT_HOTKEY = "f6"
MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
# Keys you type with: alone as a hotkey they'd fire mid-sentence, because
# keys are never blocked from other apps.
_TYPING_KEYS = {"space", "enter", "tab", "backspace"}


def make_combo(modifiers, key):
    return "+".join([m for m in MODIFIER_ORDER if m in modifiers] + [key])


def _or_list(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


def combo_problem(combo):
    """Why `combo` can't be the start/stop hotkey, or None if it's fine."""
    *mods, key = combo.split("+")
    if (key not in platforms.KEY_NAMES or key in MODIFIER_ORDER
            or any(m not in MODIFIER_ORDER for m in mods) or make_combo(mods, key) != combo):
        return "Not a valid key"
    if key == "esc":
        return "Esc is reserved for the fail-safe"
    typing = len(key) == 1 or (key.startswith("num") and key[3:].isdigit()) or key in _TYPING_KEYS
    if typing and not set(platforms.TYPING_MODIFIERS) & set(mods):
        needed = _or_list([platforms.MODIFIER_LABELS[m] for m in platforms.TYPING_MODIFIERS])
        return f"Typing keys need {needed}, or they'd fire while you type"
    return None


def display_name(combo):
    """'ctrl+page_up' -> 'Ctrl+Page Up' ('win' shows as Win or Cmd)."""
    parts = []
    for name in combo.split("+"):
        if name in platforms.MODIFIER_LABELS:
            parts.append(platforms.MODIFIER_LABELS[name])
        elif name.startswith("num") and name[3:].isdigit():
            parts.append(f"Num {name[3:]}")
        elif name.startswith("vk"):
            parts.append(f"Key {name[2:]}")
        else:
            parts.append(name.replace("_", " ").title())
    return "+".join(parts)


class HotkeyListener:
    """Calls `on_toggle` for the start/stop hotkey and `on_escape` for Esc.

    After record(on_record), the next key or combination goes to `on_record`
    instead of toggling; Esc still goes to `on_escape`. Callbacks run on the
    key source's thread and must not touch tkinter.
    """

    def __init__(self, on_toggle, on_escape, hotkey=DEFAULT_HOTKEY, source=None):
        self.hotkey = hotkey
        self._on_toggle = on_toggle
        self._on_escape = on_escape
        self._on_record = None
        self._held = set()
        self._source = source or platforms.KeySource(self._on_press, self._on_release)

    def start(self):
        self._source.start()

    def stop(self):
        self._source.stop()

    def record(self, on_record):
        self._on_record = on_record

    def stop_recording(self):
        self._on_record = None

    def _on_press(self, name, modifiers):
        if name in self._held:
            return  # ignore auto-repeat while the key is held down
        self._held.add(name)
        if name in MODIFIER_ORDER:
            return
        if name == "esc":
            self._on_escape()
            return
        combo = make_combo(modifiers, name)
        on_record, self._on_record = self._on_record, None
        if on_record is not None:
            on_record(combo)
        elif combo == self.hotkey:
            self._on_toggle()

    def _on_release(self, name):
        self._held.discard(name)
