#!/usr/bin/env python3
"""Sloth Center's Apps page (sloth_center/installed_apps.py): which folder "Also delete its settings and saved data"
may remove."""
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: (lambda f: f)
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import installed_apps  # noqa: E402


class DataDir(unittest.TestCase):
    def test_an_app_id(self):
        self.assertEqual(installed_apps.data_dir("org.mozilla.firefox", "/home/anna"),
                         Path("/home/anna/.var/app/org.mozilla.firefox"))

    def test_never_elsewhere(self):
        for bad in ("", "..", "../..", "org.x/../../etc", "firefox", "/etc/passwd", "org.x y"):
            self.assertIsNone(installed_apps.data_dir(bad, "/home/anna"), bad)


if __name__ == "__main__":
    unittest.main()
