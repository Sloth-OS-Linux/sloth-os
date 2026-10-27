#!/usr/bin/env python3
"""Programs that start at sign-in (sloth_center.startup): which are listed, and turning them off and on."""
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6; the logic is tested without it
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: None
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import startup  # noqa: E402

STEAM = """[Desktop Entry]
# written by Steam
Name=Steam
Name[hu]=Steam (magyar)
Comment=Application for managing and playing games on Steam
Exec=steam -silent %U
Icon=steam
Type=Application
X-GNOME-Autostart-enabled=true

[Desktop Action Store]
Name=Store
"""


class Startup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        startup.AUTOSTART = root / "autostart"
        startup.SYSTEM_DIRS = [root / "xdg/autostart"]
        startup.AUTOSTART.mkdir()
        startup.SYSTEM_DIRS[0].mkdir(parents=True)
        (startup.AUTOSTART / "steam.desktop").write_text(STEAM)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lists_own_programs_only(self):
        # a system part switched off by the user, and a link (not an application)
        (startup.SYSTEM_DIRS[0] / "baloo_file.desktop").write_text("[Desktop Entry]\nName=Baloo\n")
        (startup.AUTOSTART / "baloo_file.desktop").write_text("[Desktop Entry]\nHidden=true\n")
        (startup.AUTOSTART / "site.desktop").write_text("[Desktop Entry]\nType=Link\nName=Site\n")
        names = [e["name"] for e in startup.entries()]
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith("Steam"))
        self.assertTrue(startup.entries()[0]["enabled"])

    def test_turn_off_and_on_keeps_the_rest(self):
        startup.set_enabled("steam.desktop", False)
        self.assertFalse(startup.entries()[0]["enabled"])
        text = (startup.AUTOSTART / "steam.desktop").read_text()
        self.assertIn("Hidden=true", text.split("[Desktop Action Store]")[0])
        self.assertIn("# written by Steam", text)
        self.assertIn("[Desktop Action Store]\nName=Store", text)
        startup.set_enabled("steam.desktop", True)
        self.assertTrue(startup.entries()[0]["enabled"])
        self.assertNotIn("Hidden", (startup.AUTOSTART / "steam.desktop").read_text())

    def test_gnome_switch_counts_and_is_turned_back_on(self):
        (startup.AUTOSTART / "steam.desktop").write_text(STEAM.replace("enabled=true", "enabled=false"))
        self.assertFalse(startup.entries()[0]["enabled"])
        startup.set_enabled("steam.desktop", True)
        self.assertTrue(startup.entries()[0]["enabled"])

    def test_no_folder(self):
        startup.AUTOSTART = Path(self.tmp.name) / "missing"
        self.assertEqual(startup.entries(), [])


if __name__ == "__main__":
    unittest.main()
