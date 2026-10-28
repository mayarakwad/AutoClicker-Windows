"""Light/dark theming for every window: ttk styles, dropdown lists, title bars.

Light is the OS's native look ('vista' on Windows, 'aqua' on macOS). On
macOS the native look has its own dark mode; on Windows dark is ttk's
'clam' theme with our own colors. 'system' follows the OS's light/dark
setting. Status colors come from color(), so they stay readable in both.
"""
import tkinter as tk
from tkinter import ttk

from platforms import NATIVE_DARK, NATIVE_THEME, set_window_dark, system_uses_dark

MODES = ("system", "light", "dark")

PALETTES = {
    "light": {
        "running": "#107c10", "error": "#c42b1c", "recording": "#c42b1c",
        "window": "SystemButtonFace", "tip_bg": "#ffffe1", "tip_fg": "#000000",
        "list_bg": "SystemWindow", "list_fg": "SystemWindowText",
        "select_bg": "SystemHighlight", "select_fg": "SystemHighlightText",
    },
    "dark": {
        "running": "#6ccb5f", "error": "#ff7b72", "recording": "#ff7b72",
        "window": "#202020", "tip_bg": "#2b2b2b", "tip_fg": "#f0f0f0",
        "list_bg": "#2b2b2b", "list_fg": "#f0f0f0",
        "select_bg": "#264f78", "select_fg": "#ffffff",
    },
}
# Dark widget colors.
BG, FIELD, FG, MUTED, BORDER = "#202020", "#2b2b2b", "#f0f0f0", "#7a7a7a", "#3f3f3f"
BUTTON, HOVER, PRESSED, ACCENT, ACCENT_HOVER = "#2d2d2d", "#3a3a3a", "#454545", "#4c9aff", "#78b4ff"
TRACK = "#3a3a3a"  # slider track

current = "light"
_images = {}  # Tk drops PhotoImages that Python no longer references


def color(name):
    return PALETTES[current][name]


def resolve(mode):
    """'system' -> 'light' or 'dark'; other modes unchanged."""
    if mode == "system":
        return "dark" if system_uses_dark() else "light"
    return mode


def apply(root, mode):
    """Restyle the whole app (all open windows) for `mode`."""
    global current
    current = resolve(mode)
    style = ttk.Style(root)
    custom_dark = current == "dark" and not NATIVE_DARK
    if custom_dark:
        style.theme_use("clam")
        _configure_dark(style)
        _install_images(style, root)
    else:
        style.theme_use(NATIVE_THEME)
    for widget in _walk(root):
        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            style_window(widget)
        elif isinstance(widget, ttk.Combobox) and not NATIVE_DARK:
            _style_dropdown(widget)


def style_window(window):
    """Background and title bar for one window; new dialogs call this themselves."""
    if not NATIVE_DARK:  # a native dark look picks its own background
        window.configure(background=color("window"))
    set_window_dark(window, current == "dark")


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _style_dropdown(combobox):
    """A combobox's drop-down list is a plain tk Listbox that ttk styles don't reach."""
    popdown = combobox.tk.call("ttk::combobox::PopdownWindow", combobox)
    combobox.tk.call(f"{popdown}.f.l", "configure",
                     "-background", color("list_bg"), "-foreground", color("list_fg"),
                     "-selectbackground", color("select_bg"), "-selectforeground", color("select_fg"))


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _in_rounded_rect(x, y, left, top, right, bottom, radius):
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return left <= x <= right and top <= y <= bottom and (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def _raster(root, width, height, color_at, image_width=None):
    """A PhotoImage drawn by color_at(x, y) (pixel units -> '#rrggbb').

    Each pixel averages 4x4 samples, which antialiases the edges. Columns
    beyond `width` (up to `image_width`) stay transparent.
    """
    image = tk.PhotoImage(master=root, width=image_width or width, height=height)
    n = 4
    rows = []
    for py in range(height):
        row = []
        for px in range(width):
            samples = [_rgb(color_at(px + (i + 0.5) / n, py + (j + 0.5) / n)) for i in range(n) for j in range(n)]
            row.append("#%02x%02x%02x" % tuple(sum(s[k] for s in samples) // len(samples) for k in range(3)))
        rows.append("{" + " ".join(row) + "}")
    image.put(" ".join(rows), to=(0, 0))
    return image


def _check_image(root, size, fill, edge, tick):
    """A rounded checkbox on the dark background; `tick` is None for an empty box."""
    tick_points = [(x * size, y * size) for x, y in ((0.24, 0.52), (0.42, 0.70), (0.77, 0.31))]
    radius, line, half_width = 0.22 * size, 1.4, 0.075 * size

    def near_tick(x, y):
        for (ax, ay), (bx, by) in zip(tick_points, tick_points[1:]):
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
            if (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= half_width ** 2:
                return True
        return False

    def color_at(x, y):
        if not _in_rounded_rect(x, y, 0, 0, size, size, radius):
            return BG
        if not _in_rounded_rect(x, y, line, line, size - line, size - line, radius - line):
            return edge
        return tick if tick and near_tick(x, y) else fill

    # The transparent columns on the right space the label away from the box.
    return _raster(root, size, size, color_at, image_width=size + round(size * 0.45))


def _slider_image(root, width, height, fill):
    """A pill-shaped slider handle on the track."""
    def color_at(x, y):
        return fill if _in_rounded_rect(x, y, 0, 0, width, height, width / 2) else TRACK
    return _raster(root, width, height, color_at)


def _install_images(style, root):
    """Windows 11-like checkbox ticks and slider handle, in place of clam's
    ✕ marks and grip box (whose color the slider shares with the track)."""
    if "Dark.Checkbutton.indicator" in style.element_names():
        return  # elements belong to the theme and can only be created once
    scale = root.winfo_fpixels("1i") / 96
    size = max(13, round(14 * scale))
    _images.update(
        off=_check_image(root, size, FIELD, "#9a9a9a", None),
        on=_check_image(root, size, ACCENT, ACCENT, "#0b1a2e"),
        disabled_off=_check_image(root, size, BG, "#555555", None),
        disabled_on=_check_image(root, size, "#555555", "#555555", "#2b2b2b"),
        slider=_slider_image(root, round(10 * scale), round(18 * scale), ACCENT),
        slider_hover=_slider_image(root, round(10 * scale), round(18 * scale), ACCENT_HOVER),
        slider_disabled=_slider_image(root, round(10 * scale), round(18 * scale), MUTED),
    )
    style.element_create("Dark.Checkbutton.indicator", "image", _images["off"],
                         ("disabled", "selected", _images["disabled_on"]),
                         ("disabled", _images["disabled_off"]),
                         ("selected", _images["on"]), sticky="w")
    style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        ("Dark.Checkbutton.indicator", {"side": "left", "sticky": ""}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nswe"})]})]})])
    style.element_create("Dark.Scale.slider", "image", _images["slider"],
                         ("disabled", _images["slider_disabled"]), ("active", _images["slider_hover"]))
    style.layout("Horizontal.TScale", [("Horizontal.Scale.focus", {"sticky": "nswe", "children": [
        ("Horizontal.Scale.padding", {"sticky": "nswe", "children": [
            ("Horizontal.Scale.trough", {"sticky": "nswe", "children": [
                ("Dark.Scale.slider", {"side": "left", "sticky": ""})]})]})]})])


def _configure_dark(style):
    style.configure(".", background=BG, foreground=FG, fieldbackground=FIELD, bordercolor=BORDER,
                    lightcolor=BG, darkcolor=BG, troughcolor=FIELD, focuscolor=BORDER, arrowcolor=FG,
                    selectbackground=PALETTES["dark"]["select_bg"], selectforeground=FG, insertcolor=FG)
    style.map(".", foreground=[("disabled", MUTED)])

    style.configure("TButton", background=BUTTON, lightcolor=BUTTON, darkcolor=BUTTON, padding=(8, 3))
    button_states = [("disabled", BG), ("pressed", PRESSED), ("active", HOVER)]
    style.map("TButton", background=button_states, lightcolor=button_states, darkcolor=button_states,
              bordercolor=[("disabled", BORDER), ("focus", ACCENT)])

    style.configure("TEntry", lightcolor=FIELD, darkcolor=FIELD)
    style.map("TEntry", fieldbackground=[("disabled", BG)],
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", FIELD)])

    style.configure("TCombobox", background=BUTTON, lightcolor=FIELD, darkcolor=FIELD)
    style.map("TCombobox",
              fieldbackground=[("disabled", BG), ("readonly", FIELD)],
              foreground=[("disabled", MUTED), ("readonly", FG)],
              selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", FG)],
              background=[("active", HOVER)], bordercolor=[("focus", ACCENT)])

    for name in ("TCheckbutton", "TRadiobutton"):
        style.configure(name, indicatorbackground=FIELD, indicatorforeground=ACCENT,
                        upperbordercolor=BORDER, lowerbordercolor=BORDER)
        style.map(name, background=[("active", BG)],
                  indicatorbackground=[("disabled", BG), ("pressed", HOVER)],
                  indicatorforeground=[("disabled", MUTED)])

    style.configure("TLabelframe", bordercolor=BORDER, lightcolor=BG, darkcolor=BG)
    style.configure("TLabelframe.Label", background=BG, foreground=FG)

    # A flat track; the handle is an image element (see _install_images).
    style.configure("Horizontal.TScale", background=TRACK, lightcolor=TRACK, darkcolor=TRACK,
                    bordercolor=TRACK, troughcolor=TRACK)

    style.configure("Vertical.TScrollbar", background=BUTTON, troughcolor=BG, bordercolor=BG,
                    lightcolor=BUTTON, darkcolor=BUTTON)
    style.map("Vertical.TScrollbar", background=[("active", HOVER)])

    style.configure("Treeview", background=FIELD, fieldbackground=FIELD, lightcolor=FIELD, darkcolor=FIELD)
    style.map("Treeview", background=[("selected", PALETTES["dark"]["select_bg"])],
              foreground=[("selected", FG)])
    style.configure("Treeview.Heading", background=BUTTON, lightcolor=BUTTON, darkcolor=BUTTON, relief="flat")
    style.map("Treeview.Heading", background=[("active", HOVER)])
