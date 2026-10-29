"""Theme tests on a hidden Tk window."""
import gc
import sys
import tkinter as tk
import unittest
from tkinter import ttk
from unittest import mock

import theme


class ResolveTest(unittest.TestCase):
    def test_explicit_modes_pass_through(self):
        self.assertEqual(theme.resolve("light"), "light")
        self.assertEqual(theme.resolve("dark"), "dark")

    def test_system_follows_the_os(self):
        with mock.patch("theme.system_uses_dark", return_value=True):
            self.assertEqual(theme.resolve("system"), "dark")
        with mock.patch("theme.system_uses_dark", return_value=False):
            self.assertEqual(theme.resolve("system"), "light")

    def test_reading_the_os_setting_does_not_fail(self):
        self.assertIn(theme.system_uses_dark(), (True, False))


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.combo = ttk.Combobox(self.root, values=["Left", "Right"], state="readonly")
        self.combo.grid()
        self.dialog = tk.Toplevel(self.root)
        self.dialog.withdraw()

    def tearDown(self):
        theme.apply(self.root, "light")
        self.root.destroy()
        # Free the Tk interpreter here, on the main thread. Left to a later
        # garbage collection, it can be freed on whatever thread runs it
        # (e.g. subprocess's reader threads), which makes Tcl abort with
        # "Tcl_AsyncDelete: async handler deleted by the wrong thread".
        del self.root, self.combo, self.dialog
        gc.collect()

    def list_color(self):
        popdown = self.combo.tk.call("ttk::combobox::PopdownWindow", self.combo)
        return str(self.combo.tk.call(f"{popdown}.f.l", "cget", "-background"))

    @unittest.skipUnless(sys.platform == "win32", "Windows look")
    def test_windows_dark_then_light(self):
        theme.apply(self.root, "dark")
        self.assertEqual(ttk.Style(self.root).theme_use(), "clam")
        self.assertEqual(theme.current, "dark")
        self.assertEqual(theme.color("running"), theme.PALETTES["dark"]["running"])
        self.assertEqual(self.root.cget("background"), theme.BG)
        self.assertEqual(self.dialog.cget("background"), theme.BG)
        self.assertEqual(self.list_color(), theme.FIELD)

        theme.apply(self.root, "light")
        self.assertEqual(ttk.Style(self.root).theme_use(), "vista")
        self.assertEqual(theme.color("running"), theme.PALETTES["light"]["running"])
        self.assertEqual(self.list_color(), "SystemWindow")

    def test_native_dark_branch_used_on_macos(self):
        # macOS's native look has its own dark mode: no 'clam' restyling, no
        # background or drop-down overrides, just each window's appearance.
        native = ttk.Style(self.root).theme_use()
        background = self.root.cget("background")
        darkened = []  # a plain list: a Mock would keep the Tk windows alive in a reference cycle
        with mock.patch.multiple(theme, NATIVE_DARK=True, NATIVE_THEME=native,
                                 set_window_dark=lambda window, dark: darkened.append((window, dark))):
            theme.apply(self.root, "dark")
            self.assertEqual(ttk.Style(self.root).theme_use(), native)
            self.assertEqual(theme.current, "dark")
            self.assertEqual(self.root.cget("background"), background)
            self.assertIn((self.root, True), darkened)
            self.assertIn((self.dialog, True), darkened)
        darkened.clear()

    @unittest.skipUnless(sys.platform == "darwin", "macOS look")
    def test_macos_keeps_native_look_in_both_modes(self):
        theme.apply(self.root, "dark")
        self.assertEqual(ttk.Style(self.root).theme_use(), "aqua")
        self.assertEqual(theme.current, "dark")
        self.assertEqual(theme.color("running"), theme.PALETTES["dark"]["running"])
        theme.apply(self.root, "light")
        self.assertEqual(ttk.Style(self.root).theme_use(), "aqua")
        self.assertEqual(theme.current, "light")


if __name__ == "__main__":
    unittest.main()
