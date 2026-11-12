#!/usr/bin/env python3
"""Sloth Center's Accessibility and Power and battery pages without KDE: what is read from and written to KDE's
files (kdeglobals, powerdevilrc), with kreadconfig6 / kwriteconfig6 replaced by a dictionary."""
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
    qtcore.QTimer = object
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import accessibility, power  # noqa: E402


class FakeConfig:
    """kreadconfig6 / kwriteconfig6 on a dictionary: {(file, group, key): value}."""

    def __init__(self, values=None):
        self.values = dict(values or {})

    def read(self, file, group, key, default=""):
        return self.values.get((file, group, key), default)

    def write(self, file, group, key, value=None, kind=None):
        if value is None:
            self.values.pop((file, group, key), None)
        else:
            self.values[(file, group, key)] = str(value)


class TextSize(unittest.TestCase):
    def setUp(self):
        self.cfg = FakeConfig({("kdeglobals", "General", "font"): "Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"})
        accessibility.read, accessibility.write = self.cfg.read, self.cfg.write
        accessibility.notify = lambda change: None

    def test_with_size_keeps_the_rest(self):
        self.assertEqual(accessibility.with_size("Noto Sans,10,-1,5,50,0,0,0,0,0", 15),
                         "Noto Sans,15,-1,5,50,0,0,0,0,0")
        self.assertEqual(accessibility.with_size("", 12), "Noto Sans,12")

    def test_scale_from_the_default_sizes(self):
        accessibility.set_text_scale(150)
        self.assertEqual(self.cfg.values[("kdeglobals", "General", "font")], "Inter,15,-1,5,400,0,0,0,0,0,0,0,0,0,0,1")
        self.assertTrue(self.cfg.values[("kdeglobals", "General", "smallestReadableFont")].startswith("Noto Sans,12,"))
        self.assertTrue(self.cfg.values[("kdeglobals", "General", "fixed")].startswith("Noto Sans Mono,15,"))
        accessibility.set_text_scale(100)  # back: from the 100% sizes, not from the bigger ones
        self.assertEqual(self.cfg.values[("kdeglobals", "General", "font")], "Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1")

    def test_pointer_size_is_always_saved(self):
        # plasma-apply-cursortheme with the theme already in use succeeds without saving the size (HP, 2026-11-09)
        ran = []
        accessibility._run = lambda cmd: ran.append(cmd) or types.SimpleNamespace(returncode=0, stdout="")
        accessibility.set_cursor_size(48)
        self.assertEqual(str(self.cfg.values[("kcminputrc", "Mouse", "cursorSize")]), "48")
        self.assertTrue(any(c[0] == "plasma-apply-cursortheme" for c in ran))


class PowerSettings(unittest.TestCase):
    def setUp(self):
        self.cfg = FakeConfig()
        power.read, power.write = self.cfg.read, self.cfg.write

    def test_not_chosen_is_kdes_default(self):
        self.assertEqual(power.screen_off("AC"), -1)
        self.assertEqual(power.sleep_after("Battery"), -1)

    def test_screen_off(self):
        power.set_screen_off("Battery", 5)
        self.assertEqual(self.cfg.values[("powerdevilrc", "Battery][Display", "TurnOffDisplayWhenIdle")], "true")
        self.assertEqual(self.cfg.values[("powerdevilrc", "Battery][Display", "TurnOffDisplayIdleTimeoutSec")], "300")
        self.assertEqual(power.screen_off("Battery"), 5)
        power.set_screen_off("Battery", 0)
        self.assertEqual(power.screen_off("Battery"), 0)  # never
        power.set_screen_off("Battery", -1)
        self.assertEqual(power.screen_off("Battery"), -1)  # back to KDE's own
        self.assertNotIn(("powerdevilrc", "Battery][Display", "TurnOffDisplayIdleTimeoutSec"), self.cfg.values)

    def test_sleep(self):
        power.set_sleep_after("AC", 60)
        self.assertEqual(self.cfg.values[("powerdevilrc", "AC][SuspendAndShutdown", "AutoSuspendAction")], "1")
        self.assertEqual(power.sleep_after("AC"), 60)
        power.set_sleep_after("AC", 0)
        self.assertEqual(self.cfg.values[("powerdevilrc", "AC][SuspendAndShutdown", "AutoSuspendAction")], "0")
        self.assertEqual(power.sleep_after("AC"), 0)

    def test_lid_and_button_everywhere(self):
        power.set_action("LidAction", power.TURN_OFF_SCREEN)
        for source in ("AC", "Battery", "LowBattery"):
            self.assertEqual(self.cfg.values[("powerdevilrc", f"{source}][SuspendAndShutdown", "LidAction")], "64")
        self.assertEqual(power.action("LidAction", power.LID_CHOICES, power.SLEEP), power.TURN_OFF_SCREEN)
        self.cfg.values[("powerdevilrc", "AC][SuspendAndShutdown", "PowerButtonAction")] = "32"  # set elsewhere
        self.assertEqual(power.action("PowerButtonAction", power.BUTTON_CHOICES, power.ASK), power.ASK)


if __name__ == "__main__":
    unittest.main(verbosity=2)
