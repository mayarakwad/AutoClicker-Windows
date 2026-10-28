"""Windows backend: pynput for hooks and plain clicks, Win32 (ctypes) for the rest.

All coordinates are physical pixels: prepare_process() makes the process
DPI-aware before any window exists.
"""
import ctypes
import ctypes.wintypes as wt
import os
import threading
import tkinter as tk
import winreg
import winsound
from pathlib import Path

from pynput import keyboard, mouse
from pynput.mouse import Button

OS_NAME = "Windows"
NATIVE_THEME = "vista"
NATIVE_DARK = False  # 'vista' has no dark mode; theme.py styles 'clam' instead
MODIFIER_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
TYPING_MODIFIERS = ("ctrl", "alt")  # Win+letter is mostly taken by Windows itself
EXAMPLE_COMBO = "ctrl+shift+s"

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")


# --- Process, files, look ---------------------------------------------------

def prepare_process():
    """Use real pixel coordinates on scaled (125%, 150%) displays.

    Must run before any window is created; pynput doesn't do this itself.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor aware
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def set_clicking(active):
    pass  # Windows doesn't throttle the click timer: time.sleep uses a high-resolution timer


def set_app_icon(root, assets):
    try:
        root.iconbitmap(default=assets / "app.ico")  # default= covers dialogs too
    except tk.TclError:
        pass


def settings_folder():
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "AutoClicker"


def system_uses_dark():
    """Windows' app mode (Settings > Personalization > Colors)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


DWMWA_USE_IMMERSIVE_DARK_MODE = 20
SWP_REDRAW_FRAME = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # no size/move/z-order/activate; frame changed
user32.GetParent.argtypes = (wt.HWND,)
user32.GetParent.restype = wt.HWND
user32.SetWindowPos.argtypes = (wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT)
dwmapi.DwmSetWindowAttribute.argtypes = (wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD)


def set_window_dark(window, dark):
    """Dark or light title bar for one Tk window."""
    window.update_idletasks()
    hwnd = user32.GetParent(window.winfo_id())
    if hwnd:
        value = ctypes.c_int(dark)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        # Repaint the frame now rather than on the next focus change.
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_REDRAW_FRAME)


START_TONES = ((660, 60), (990, 80))  # rising: (Hz, ms)
STOP_TONES = ((990, 60), (660, 80))   # falling


def play_sound(started):
    """Start/stop beep on a background thread, so the UI never waits."""
    tones = START_TONES if started else STOP_TONES
    threading.Thread(target=_beep, args=(tones,), daemon=True).start()


def _beep(tones):
    try:
        for hz, ms in tones:
            winsound.Beep(hz, ms)
    except RuntimeError:
        pass  # no sound device


def permission_problem():
    return None  # Windows needs no special permission for global input


def request_permissions():
    pass


# --- Screens and windows ----------------------------------------------------

MONITOR_DEFAULTTONULL = 0
user32.MonitorFromPoint.argtypes = (wt.POINT, wt.DWORD)
user32.MonitorFromPoint.restype = wt.HMONITOR
user32.WindowFromPoint.argtypes = (wt.POINT,)
user32.WindowFromPoint.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
user32.GetWindowThreadProcessId.restype = wt.DWORD


def on_screen(x, y):
    return bool(user32.MonitorFromPoint(wt.POINT(x, y), MONITOR_DEFAULTTONULL))


def is_own_window(x, y):
    """Whether the window at (x, y) belongs to this app (e.g. its own Stop button)."""
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(user32.WindowFromPoint(wt.POINT(x, y)), ctypes.byref(pid))
    return pid.value == os.getpid()


# --- Mouse output -----------------------------------------------------------

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
BUTTONS = {  # name -> (pynput button, SendInput down flag, up flag)
    "left": (Button.left, 0x0002, 0x0004),
    "right": (Button.right, 0x0008, 0x0010),
    "middle": (Button.middle, 0x0020, 0x0040),
}
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    # The real INPUT holds a union; MOUSEINPUT is its largest member, so the
    # size and layout match.
    _fields_ = [("type", wt.DWORD), ("mi", MOUSEINPUT)]


user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wt.UINT


def normalize(value, origin, size):
    """Pixel -> SendInput absolute coordinate (0..65535 across the virtual desktop).

    Windows maps back with n * size // 65536, so round up to land exactly
    on the requested pixel.
    """
    return ((value - origin) * 65536 + size - 1) // size


def _move(x, y):
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    return INPUT(INPUT_MOUSE, MOUSEINPUT(normalize(x, left, width), normalize(y, top, height), 0, flags, 0, 0))


def _button(flag):
    return INPUT(INPUT_MOUSE, MOUSEINPUT(0, 0, 0, flag, 0, 0))


def _send(inputs):
    user32.SendInput(len(inputs), (INPUT * len(inputs))(*inputs), ctypes.sizeof(INPUT))


class Mouse:
    """Mouse output used by the click engine. Buttons are 'left', 'right', 'middle'.

    Clicks at the cursor go through pynput. Clicks at a fixed point are one
    SendInput batch (move there, click, move back), so the click can't land
    anywhere else and the user keeps the cursor, which also keeps the
    top-left-corner fail-safe reachable.
    """

    def __init__(self):
        self._controller = mouse.Controller()

    @property
    def position(self):
        return self._controller.position

    def click(self, button, count=1):
        self._controller.click(BUTTONS[button][0], count)

    def click_at(self, x, y, button, count=1):
        """Click at (x, y), then put the cursor back where it was."""
        home = self.position
        _, down, up = BUTTONS[button]
        inputs = [_move(x, y)]
        for _ in range(count):
            inputs += [_button(down), _button(up)]
        inputs.append(_move(*home))
        # One batch keeps the move and click together. (Moving the physical
        # mouse at that very instant can still nudge the click a few pixels.)
        _send(inputs)


# --- Mouse input ------------------------------------------------------------

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
_BUTTON_NAMES = {button: name for name, (button, _, _) in BUTTONS.items()}


class PointPicker:
    """Captures the next left click anywhere on screen and swallows it.

    `on_pick(x, y)` runs on pynput's hook thread and must not touch tkinter.
    """

    def __init__(self, on_pick):
        self._on_pick = on_pick
        self._picked = False
        self._listener = mouse.Listener(win32_event_filter=self._filter)
        self._listener.daemon = True

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def _filter(self, msg, data):
        if msg == WM_LBUTTONDOWN and not self._picked:
            self._picked = True
            self._on_pick(data.pt.x, data.pt.y)
            self._listener.suppress_event()
        elif msg == WM_LBUTTONUP and self._picked:
            self._listener.stop()
            self._listener.suppress_event()


class MouseListener:
    """Left/right/middle presses anywhere: on_press(x, y, button_name).

    Clicks still reach the app underneath. Runs on pynput's listener thread.
    """

    def __init__(self, on_press):
        self._on_press = on_press
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.daemon = True

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def _on_click(self, x, y, button, pressed):
        name = _BUTTON_NAMES.get(button)
        if pressed and name:
            self._on_press(x, y, name)


# --- Keyboard ---------------------------------------------------------------

_MODIFIER_VKS = {"ctrl": (0x11, 0xA2, 0xA3), "alt": (0x12, 0xA4, 0xA5),
                 "shift": (0x10, 0xA0, 0xA1), "win": (0x5B, 0x5C)}
_VK_MODIFIER = {vk: name for name, vks in _MODIFIER_VKS.items() for vk in vks}
_SPECIAL = {
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x13: "pause", 0x14: "caps_lock",
    0x1B: "esc", 0x20: "space", 0x21: "page_up", 0x22: "page_down", 0x23: "end",
    0x24: "home", 0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down",
    0x2C: "print_screen", 0x2D: "insert", 0x2E: "delete", 0x5D: "menu",
    0x6A: "num_multiply", 0x6B: "num_add", 0x6D: "num_subtract", 0x6E: "num_decimal",
    0x6F: "num_divide", 0x90: "num_lock", 0x91: "scroll_lock",
}
user32.GetAsyncKeyState.restype = ctypes.c_short


def vk_name(vk):
    """Key name from a Windows virtual-key code (layout-independent for F-keys etc.)."""
    if vk in _VK_MODIFIER:
        return _VK_MODIFIER[vk]
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x60 <= vk <= 0x69:
        return f"num{vk - 0x60}"
    return _SPECIAL.get(vk, f"vk{vk}")


KEY_NAMES = {vk_name(vk) for vk in range(1, 256)}


def key_name(key):
    """Name of a pynput key event, or None if it has no virtual-key code.

    Uses the vk, never pynput's char: with Ctrl held, Ctrl+A's char is '\\x01'.
    """
    vk = key.value.vk if isinstance(key, keyboard.Key) else getattr(key, "vk", None)
    return vk_name(vk) if vk is not None else None


def held_modifiers():
    """Modifiers held right now, asked from Windows so a missed key-up
    (e.g. after Ctrl+Alt+Del or a UAC prompt) can't leave one stuck."""
    return {name for name, vks in _MODIFIER_VKS.items()
            if any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks)}


class KeySource:
    """Global key events as names: on_press(name, modifiers), on_release(name).

    Keys are only observed, never blocked. Runs on pynput's listener thread.
    """

    def __init__(self, on_press, on_release):
        self._on_press = on_press
        self._on_release = on_release
        self._listener = None

    def start(self):
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()

    def _press(self, key):
        name = key_name(key)
        if name is not None:
            self._on_press(name, held_modifiers())

    def _release(self, key):
        name = key_name(key)
        if name is not None:
            self._on_release(name)
