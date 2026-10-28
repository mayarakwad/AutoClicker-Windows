"""Windows backend tests that send no input (key naming, coordinates, screens, sounds)."""
import sys
import time
import unittest
from unittest import mock

if sys.platform == "win32":
    from pynput.keyboard import Key, KeyCode

    from platforms import windows


@unittest.skipUnless(sys.platform == "win32", "Windows backend")
class KeyNameTest(unittest.TestCase):
    def test_special_keys(self):
        self.assertEqual(windows.key_name(Key.f6), "f6")
        self.assertEqual(windows.key_name(Key.f24), "f24")
        self.assertEqual(windows.key_name(Key.page_up), "page_up")
        self.assertEqual(windows.key_name(Key.esc), "esc")

    def test_left_and_right_modifiers_share_a_name(self):
        self.assertEqual(windows.key_name(Key.ctrl_l), "ctrl")
        self.assertEqual(windows.key_name(Key.ctrl_r), "ctrl")
        self.assertEqual(windows.key_name(Key.alt_gr), "alt")
        self.assertEqual(windows.key_name(Key.shift_r), "shift")
        self.assertEqual(windows.key_name(Key.cmd), "win")

    def test_letters_come_from_vk_not_char(self):
        # With Ctrl held, Windows reports Ctrl+A's char as '\x01'.
        self.assertEqual(windows.key_name(KeyCode(vk=0x41, char="\x01")), "a")
        self.assertEqual(windows.key_name(KeyCode(vk=0x37, char="&")), "7")
        self.assertEqual(windows.key_name(KeyCode.from_vk(0x65)), "num5")
        self.assertEqual(windows.key_name(KeyCode.from_vk(0xBB)), "vk187")

    def test_key_source_reports_names_and_modifiers(self):
        pressed, released = [], []
        source = windows.KeySource(lambda name, mods: pressed.append((name, mods)), released.append)
        with mock.patch.object(windows, "held_modifiers", return_value={"ctrl"}):
            source._press(KeyCode(vk=0x53, char="\x13"))
        source._release(Key.f6)
        self.assertEqual(pressed, [("s", {"ctrl"})])
        self.assertEqual(released, ["f6"])


@unittest.skipUnless(sys.platform == "win32", "Windows backend")
class ScreenTest(unittest.TestCase):
    def test_normalize_round_trips_to_the_same_pixel(self):
        # Windows maps n back to a pixel as n * size // 65536.
        for origin, size in ((0, 1920), (0, 1080), (-1920, 3840), (-1440, 2520), (0, 7680)):
            for value in range(origin, origin + size):
                n = windows.normalize(value, origin, size)
                self.assertLessEqual(n, 65535)
                self.assertEqual(n * size // 65536 + origin, value)

    def test_on_screen(self):
        self.assertTrue(windows.on_screen(0, 0))
        self.assertFalse(windows.on_screen(-99999, -99999))

    def test_mouse_listener_reports_button_names(self):
        from pynput.mouse import Button
        presses = []
        listener = windows.MouseListener(lambda x, y, button: presses.append((x, y, button)))
        listener._on_click(1, 2, Button.left, True)
        listener._on_click(1, 2, Button.left, False)  # release: ignored
        listener._on_click(3, 4, Button.x1, True)    # side button: ignored
        listener._on_click(5, 6, Button.middle, True)
        self.assertEqual(presses, [(1, 2, "left"), (5, 6, "middle")])


@unittest.skipUnless(sys.platform == "win32", "Windows backend")
class SoundTest(unittest.TestCase):
    def play_and_collect(self, started):
        with mock.patch.object(windows.winsound, "Beep") as beep:
            began = time.perf_counter()
            windows.play_sound(started)
            returned_after = time.perf_counter() - began
            deadline = time.perf_counter() + 1
            while beep.call_count < 2 and time.perf_counter() < deadline:
                time.sleep(0.01)
        return [c.args for c in beep.call_args_list], returned_after

    def test_start_rises_stop_falls(self):
        tones, _ = self.play_and_collect(True)
        self.assertEqual(tones, list(windows.START_TONES))
        self.assertLess(tones[0][0], tones[1][0])
        tones, _ = self.play_and_collect(False)
        self.assertEqual(tones, list(windows.STOP_TONES))
        self.assertGreater(tones[0][0], tones[1][0])

    def test_play_does_not_wait_for_the_beep(self):
        _, returned_after = self.play_and_collect(True)
        self.assertLess(returned_after, 0.05)

    def test_missing_sound_device_is_ignored(self):
        with mock.patch.object(windows.winsound, "Beep", side_effect=RuntimeError("no device")):
            windows._beep(windows.START_TONES)  # must not raise


if __name__ == "__main__":
    unittest.main()
