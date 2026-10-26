#!/usr/bin/env python3
"""The FPS display's settings (sloth_common.gamesettings.ensure_overlay_config): written once, never overwritten."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import gamesettings  # noqa: E402


class OverlayConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.config = self.home / ".config"

    def tearDown(self):
        self.tmp.cleanup()

    def test_written_with_temperatures(self):
        written = gamesettings.ensure_overlay_config(self.home, self.config)
        self.assertEqual(written, [self.config / "MangoHud/MangoHud.conf"])
        text = written[0].read_text()
        for key in ("fps", "cpu_stats", "cpu_temp", "gpu_stats", "gpu_temp"):
            self.assertIn(f"\n{key}\n", text)

    def test_steam_folder_too_when_steam_is_there(self):
        (self.home / ".var/app/com.valvesoftware.Steam").mkdir(parents=True)
        written = gamesettings.ensure_overlay_config(self.home, self.config)
        self.assertIn(self.home / ".var/app/com.valvesoftware.Steam/config/MangoHud/MangoHud.conf", written)

    def test_own_settings_are_kept(self):
        own = self.config / "MangoHud/MangoHud.conf"
        own.parent.mkdir(parents=True)
        own.write_text("fps_only\n")
        self.assertEqual(gamesettings.ensure_overlay_config(self.home, self.config), [])
        self.assertEqual(own.read_text(), "fps_only\n")


if __name__ == "__main__":
    unittest.main()
