#!/usr/bin/env python3
"""Display and sound profiles (sloth_center.profiles): capturing the setup and the kscreen-doctor arguments."""
import sys
import tempfile
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

from sloth_center import profiles  # noqa: E402

WIDE, FULL, TV = {"width": 3440, "height": 1440}, {"width": 1920, "height": 1080}, {"width": 3840, "height": 2160}


def screens(dp_on=True, hdmi_on=True, tv=False):
    """As kscreen-doctor -j printed it on a real machine (2026-10-27), with a TV that can be plugged in."""
    outs = [
        {"name": "DP-4", "connected": True, "enabled": dp_on, "currentModeId": "2", "pos": {"x": 1920, "y": 0},
         "scale": 1, "priority": 1,
         "modes": [{"id": "1", "size": WIDE, "refreshRate": 59.97}, {"id": "2", "size": WIDE, "refreshRate": 144.001}]},
        {"name": "HDMI-A-2", "connected": True, "enabled": hdmi_on, "currentModeId": "36", "pos": {"x": 0, "y": 232},
         "scale": 1, "priority": 2,
         "modes": [{"id": "36", "size": FULL, "refreshRate": 60.0}, {"id": "37", "size": FULL, "refreshRate": 59.94}]},
    ]
    if tv:
        outs.append({"name": "HDMI-A-1", "connected": True, "enabled": False, "currentModeId": "", "pos": {"x": 0, "y": 0},
                     "scale": 1, "priority": 0,
                     "modes": [{"id": "70", "size": TV, "refreshRate": 60.0}, {"id": "71", "size": TV, "refreshRate": 120.0}]})
    return {"outputs": outs}


class Profiles(unittest.TestCase):
    def test_capture(self):
        p = profiles.capture("  Desk ", screens(), "sink.headset", "source.webcam")
        self.assertEqual(p["name"], "Desk")
        self.assertEqual([(d["connector"], d["enabled"]) for d in p["displays"]], [("DP-4", True), ("HDMI-A-2", True)])
        self.assertEqual((p["displays"][0]["width"], p["displays"][0]["refresh"], p["displays"][0]["x"]), (3440, 144.0, 1920))
        self.assertEqual((p["sink"], p["source"]), ("sink.headset", "source.webcam"))

    def test_apply_again_by_size_and_refresh(self):
        desk = profiles.capture("Desk", screens())
        args, missing = profiles.display_args(desk, screens())
        self.assertIn("output.DP-4.mode.2", args)          # 144 Hz, found by size and refresh, not by the old id
        self.assertIn("output.DP-4.position.1920,0", args)
        self.assertIn("output.DP-4.priority.1", args)
        self.assertEqual(missing, [])

    def test_turning_on_comes_before_turning_off(self):
        tv = {"name": "TV", "displays": [
            {"connector": "DP-4", "enabled": False}, {"connector": "HDMI-A-2", "enabled": False},
            {"connector": "HDMI-A-1", "enabled": True, "width": 3840, "height": 2160, "refresh": 120.0,
             "x": 0, "y": 0, "scale": 1.5, "priority": 1}]}
        args, _ = profiles.display_args(tv, screens(tv=True))
        self.assertEqual(args[:5], ["output.HDMI-A-1.enable", "output.HDMI-A-1.mode.71",
                                    "output.HDMI-A-1.position.0,0", "output.HDMI-A-1.scale.1.5",
                                    "output.HDMI-A-1.priority.1"])
        self.assertEqual(args[5:], ["output.DP-4.disable", "output.HDMI-A-2.disable"])

    def test_a_missing_screen_is_left_out(self):
        tv = {"name": "TV", "displays": [
            {"connector": "HDMI-A-1", "enabled": True, "width": 3840, "height": 2160, "refresh": 60},
            {"connector": "DP-4", "enabled": True, "width": 3440, "height": 1440, "refresh": 144}]}
        args, missing = profiles.display_args(tv, screens())
        self.assertEqual(missing, ["HDMI-A-1"])
        self.assertTrue(args and all("HDMI-A-1" not in a for a in args))

    def test_never_everything_off(self):
        tv_only = {"name": "TV", "displays": [
            {"connector": "HDMI-A-1", "enabled": True, "width": 3840, "height": 2160, "refresh": 60},
            {"connector": "DP-4", "enabled": False}, {"connector": "HDMI-A-2", "enabled": False}]}
        self.assertEqual(profiles.display_args(tv_only, screens()), ([], ["HDMI-A-1"]))

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sloth-os/profiles.json"
            self.assertEqual(profiles.load(path), [])
            profiles.save([profiles.capture("Desk", screens())], path)
            self.assertEqual([p["name"] for p in profiles.load(path)], ["Desk"])
            path.write_text("not json")
            self.assertEqual(profiles.load(path), [])


if __name__ == "__main__":
    unittest.main()
