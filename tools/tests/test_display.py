#!/usr/bin/env python3
"""Displays (sloth_center.display): monitor names, the best refresh rate, VRR and HDR, from kscreen-doctor output."""
import json
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6; the rest is tested without it
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: (lambda f: f)  # as a decorator and as a plain call
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import display  # noqa: E402

WIDE, FULL = {"width": 3440, "height": 1440}, {"width": 1920, "height": 1080}
# As kscreen-doctor printed them on a real machine (2026-10-26): a 144 Hz monitor running at 100 Hz, HDR off
JSON = {"outputs": [
    {"id": 1, "name": "DP-4", "connected": True, "enabled": True, "currentModeId": "7", "hdr": False,
     "modes": [{"id": "1", "name": "3440x1440@60", "size": WIDE, "refreshRate": 59.97},
               {"id": "7", "name": "3440x1440@100", "size": WIDE, "refreshRate": 99.982},
               {"id": "2", "name": "3440x1440@144", "size": WIDE, "refreshRate": 144.001},
               {"id": "3", "name": "1920x1080@240", "size": FULL, "refreshRate": 240.0}]},
    {"id": 2, "name": "HDMI-A-2", "connected": True, "enabled": True, "currentModeId": "36",
     "modes": [{"id": "36", "name": "1920x1080@60", "size": FULL, "refreshRate": 60.0},
               {"id": "37", "name": "1920x1080@60", "size": FULL, "refreshRate": 59.94}]},
    {"id": 3, "name": "DP-5", "connected": False, "enabled": False, "currentModeId": "", "modes": []},
]}
TEXT = """\x1b[01;32mOutput: \x1b[0;0m1 DP-4 2caae1c6
\tenabled
\tVrr: Automatic
\tHDR: disabled
Output: 2 HDMI-A-2 ccba1f77
\tVrr: incapable
\tHDR: incapable
"""


def run(cmd):
    return json.dumps(JSON) if cmd[-1] == "-j" else TEXT


class Outputs(unittest.TestCase):
    def setUp(self):
        self.monitors = display.outputs(run, name_of={"DP-4": "U34G3XM", "HDMI-A-2": "DELL S2715H"}.get)

    def test_only_connected_ones_by_their_names(self):
        self.assertEqual([m["name"] for m in self.monitors], ["U34G3XM", "DELL S2715H"])

    def test_best_refresh_at_the_same_size(self):
        wide = self.monitors[0]
        self.assertEqual((wide["hz"], wide["bestHz"], wide["bestMode"], wide["previousMode"]), (100, 144, "2", "7"))
        self.assertEqual(wide["size"], "3440×1440")

    def test_vrr_and_hdr_only_where_supported(self):
        self.assertEqual((self.monitors[0]["vrr"], self.monitors[0]["hdr"]), ("on", "off"))
        self.assertEqual((self.monitors[1]["vrr"], self.monitors[1]["hdr"]), ("", ""))

    def test_kscreen_doctor_missing(self):
        self.assertEqual(display.outputs(lambda cmd: ""), [])


class Edid(unittest.TestCase):
    def test_monitor_name_descriptor(self):
        edid = bytearray(128)
        edid[72:90] = b"\0\0\0\xfc\0" + b"DELL S2715H\n  "
        self.assertEqual(display.edid_name(bytes(edid)), "DELL S2715H")
        self.assertEqual(display.edid_name(b"short"), "")


if __name__ == "__main__":
    unittest.main()
