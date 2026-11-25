#!/usr/bin/env python3
"""The Windows programs on the Updates page (sloth_center/winupdates.py): the newest runtime installed, and the
programs the .exe handler keeps on an earlier one because the newest did not start them."""
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
try:  # only the Qt part needs PySide6
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.QTimer = object
    qtcore.Property = lambda *a, **k: (lambda f: f)
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import winupdates as wu  # noqa: E402


def app(name, launch):
    return types.SimpleNamespace(name=name, meta={"launch": launch})


class WinUpdates(unittest.TestCase):
    def test_newest_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("UMU-Proton-9.0-3", "UMU-Proton-10.0-4", "UMU-Proton-10.0-12", "GE-Proton10-20", "UMU-Proton-11.0-1"):
                (base / name).mkdir()
                if name != "UMU-Proton-11.0-1":      # a half-downloaded one does not count
                    (base / name / "proton").write_text("")
            self.assertEqual(wu.newest_runtime([base]), "UMU-Proton-10.0-12")
            self.assertEqual(wu.newest_runtime([base / "missing"]), "")

    def test_held_back(self):
        newest = "UMU-Proton-10.0-12"
        apps = [
            # the newest was tried and failed, an older one works: kept back
            app("Battle.net", {"Battle.net.exe": {"good": {"proton": "UMU-Proton-10.0-4", "profile": "default"},
                                                  "failed": [f"{newest}|default"]}}),
            # works with the newest
            app("EA app", {"EADesktop.exe": {"good": {"proton": newest, "profile": "default"}, "failed": []}}),
            # an older one works, but the newest was not tried yet (it is tried at the next start): not said
            app("Old game", {"game.exe": {"good": {"proton": "UMU-Proton-9.0-3"}, "failed": []}}),
            # GE-Proton by choice: not about the update
            app("Modded", {"m.exe": {"good": {"proton": "GE-Proton10-20"}, "failed": [f"{newest}|default"]}}),
            app("Never started", {}),
        ]
        self.assertEqual(wu.held_back(apps, newest), ["Battle.net"])
        self.assertEqual(wu.held_back(apps, ""), [])


if __name__ == "__main__":
    unittest.main()
