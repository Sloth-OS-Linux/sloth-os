#!/usr/bin/env python3
"""Sloth OS settings in a file (sloth_center.settings_backup): collect, read, restore."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6 (and gi for the look); the rest is tested without them
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.QUrl = None
    qtcore.Property = lambda *a, **k: (lambda f: f)  # as a decorator and as a plain call
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore
try:
    import gi.repository  # noqa: F401
except ImportError:
    gi = types.ModuleType("gi")
    gi.repository = types.ModuleType("gi.repository")
    gi.repository.Gio = gi.repository.GLib = None
    sys.modules["gi"], sys.modules["gi.repository"] = gi, gi.repository

from sloth_center import settings_backup as sb  # noqa: E402


class SettingsBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.old, self.new = root / "old", root / "new"
        self.old.mkdir()
        self.drive = root / "Games"
        self.drive.mkdir()
        (self.old / "community.json").write_text('{"share": true}')
        (self.old / "profiles.json").write_text('[{"name": "TV", "displays": [], "sink": "", "source": ""}]')
        (self.old / "applications.json").write_text(json.dumps(
            {"libraries": [str(self.drive), "/var/mnt/gone"], "default": str(self.drive)}))
        (self.old / "welcome-done").write_text("")
        (self.old / "broken.json").write_text("{")

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        backup = sb.collect(self.old, {"scheme": "SlothNight", "layout": "ubuntu"})
        self.assertEqual(sorted(backup["files"]), ["applications.json", "community.json", "profiles.json"])
        path = Path(self.tmp.name) / "Sloth OS settings.json"
        sb.write(path, backup)
        read = sb.read(path)
        self.assertEqual(read["appearance"], {"scheme": "SlothNight", "layout": "ubuntu"})
        written = sb.restore(read, self.new)
        self.assertEqual(sorted(written), ["applications.json", "community.json", "profiles.json"])
        self.assertEqual(json.loads((self.new / "community.json").read_text()), {"share": True})

    def test_program_places_only_where_the_drive_exists(self):
        self.new.mkdir()
        (self.new / "applications.json").write_text('{"libraries": ["/var/home/me/Applications"]}')
        sb.restore(sb.collect(self.old), self.new)
        apps = json.loads((self.new / "applications.json").read_text())
        self.assertEqual(apps["libraries"], [str(self.drive), "/var/home/me/Applications"])
        self.assertEqual(apps["default"], str(self.drive))

    def test_only_our_own_files(self):
        backup = sb.collect(self.old)
        backup["files"]["../../.bashrc"] = {"evil": True}
        backup["files"]["welcome-done"] = {}
        self.assertNotIn("../../.bashrc", sb.restore(backup, self.new))
        self.assertFalse((self.new / "welcome-done").exists())
        self.assertFalse((Path(self.tmp.name) / ".bashrc").exists())

    def test_not_a_backup(self):
        other = Path(self.tmp.name) / "other.json"
        other.write_text('{"files": {}}')
        self.assertIsNone(sb.read(other))
        other.write_text("not json")
        self.assertIsNone(sb.read(other))
        self.assertIsNone(sb.read(Path(self.tmp.name) / "missing.json"))


if __name__ == "__main__":
    unittest.main()
