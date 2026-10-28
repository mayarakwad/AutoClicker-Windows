"""Hotkey logic tests. Key events are fed in as names; no real keyboard hook."""
import unittest

import platforms
from hotkeys import HotkeyListener, combo_problem, display_name, make_combo


class FakeSource:
    def start(self):
        pass

    def stop(self):
        pass


class ComboTest(unittest.TestCase):
    def test_make_combo_orders_modifiers(self):
        self.assertEqual(make_combo({"shift", "ctrl"}, "f6"), "ctrl+shift+f6")
        self.assertEqual(make_combo({"win", "alt"}, "f6"), "alt+win+f6")
        self.assertEqual(make_combo(set(), "f6"), "f6")

    def test_valid_hotkeys(self):
        for combo in ("f6", "f12", "ctrl+shift+s", "alt+1", "page_down", "ctrl+num5", "home", "shift+f8"):
            self.assertIsNone(combo_problem(combo), combo)

    def test_esc_is_reserved(self):
        self.assertIn("fail-safe", combo_problem("esc"))
        self.assertIn("fail-safe", combo_problem("ctrl+esc"))

    def test_typing_keys_need_a_modifier(self):
        for combo in ("s", "shift+s", "1", "space", "enter", "num5"):
            self.assertIn("Ctrl", combo_problem(combo), combo)

    def test_malformed(self):
        for combo in ("", "ctrl", "foo", "shift+ctrl+f6", "ctrl+ctrl+f6", "hyper+f6", "f6+ctrl"):
            self.assertEqual(combo_problem(combo), "Not a valid key", combo)

    def test_display_name(self):
        alt, win = platforms.MODIFIER_LABELS["alt"], platforms.MODIFIER_LABELS["win"]
        self.assertEqual(display_name("f6"), "F6")
        self.assertEqual(display_name("ctrl+shift+f6"), "Ctrl+Shift+F6")
        self.assertEqual(display_name("page_up"), "Page Up")
        self.assertEqual(display_name("alt+num5"), f"{alt}+Num 5")
        self.assertEqual(display_name("win+a"), f"{win}+A")
        self.assertEqual(display_name("vk187"), "Key 187")


class HotkeyListenerTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.recorded = []
        self.listener = HotkeyListener(on_toggle=lambda: self.events.append("toggle"),
                                       on_escape=lambda: self.events.append("escape"),
                                       source=FakeSource())

    def tap(self, name, modifiers=()):
        self.listener._on_press(name, set(modifiers))
        self.listener._on_release(name)

    def test_hotkey_toggles(self):
        self.tap("f6")
        self.tap("f6")
        self.assertEqual(self.events, ["toggle", "toggle"])

    def test_auto_repeat_is_ignored(self):
        for _ in range(5):
            self.listener._on_press("f6", set())
        self.listener._on_release("f6")
        self.assertEqual(self.events, ["toggle"])

    def test_modifiers_must_match_exactly(self):
        self.listener.hotkey = "ctrl+f6"
        self.tap("f6")
        self.tap("f6", {"ctrl", "shift"})
        self.assertEqual(self.events, [])
        self.tap("f6", {"ctrl"})
        self.assertEqual(self.events, ["toggle"])

    def test_plain_hotkey_ignores_modified_press(self):
        self.tap("f6", {"ctrl"})
        self.assertEqual(self.events, [])

    def test_escape_fires_with_any_modifiers(self):
        self.tap("esc")
        self.tap("esc", {"shift"})
        self.assertEqual(self.events, ["escape", "escape"])

    def test_record_captures_next_combo_once(self):
        self.listener.record(self.recorded.append)
        self.tap("ctrl")  # modifiers alone don't end recording
        self.tap("s", {"ctrl", "shift"})
        self.assertEqual(self.recorded, ["ctrl+shift+s"])
        self.tap("f6")
        self.assertEqual(self.recorded, ["ctrl+shift+s"])
        self.assertEqual(self.events, ["toggle"])

    def test_recording_the_current_hotkey_does_not_toggle(self):
        self.listener.record(self.recorded.append)
        self.tap("f6")
        self.assertEqual(self.recorded, ["f6"])
        self.assertEqual(self.events, [])

    def test_esc_while_recording_goes_to_escape(self):
        self.listener.record(self.recorded.append)
        self.tap("esc")
        self.assertEqual(self.events, ["escape"])
        self.listener.stop_recording()
        self.tap("f6")
        self.assertEqual(self.recorded, [])
        self.assertEqual(self.events, ["escape", "toggle"])


if __name__ == "__main__":
    unittest.main()
