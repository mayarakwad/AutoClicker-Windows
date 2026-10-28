"""Settings file tests (temporary folder, never the real settings file)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "AutoClicker" / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip_creates_folder(self):
        data = {"millis": "250", "use_offset": True, "x": "-300", "hotkey": "ctrl+f8"}
        settings.save(data, self.path)
        self.assertEqual(settings.load(self.path), data)
        self.assertEqual(os.listdir(self.path.parent), ["settings.json"])

    def test_missing_file_gives_empty(self):
        self.assertEqual(settings.load(self.path), {})

    def test_unreadable_contents_give_empty(self):
        self.path.parent.mkdir(parents=True)
        for content in (b"{not json", b"\xff\xfe\x00garbage", b"[1, 2]", b""):
            self.path.write_bytes(content)
            self.assertEqual(settings.load(self.path), {}, content)

    def test_default_path(self):
        path = settings.default_path()
        self.assertEqual((path.parent.name, path.name), ("AutoClicker", "settings.json"))
        if sys.platform == "win32":
            self.assertEqual(path.parent.parent, Path(os.environ["APPDATA"]))
        elif sys.platform == "darwin":
            self.assertEqual(path.parent.parent, Path.home() / "Library" / "Application Support")


if __name__ == "__main__":
    unittest.main()
