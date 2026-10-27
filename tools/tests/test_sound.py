#!/usr/bin/env python3
"""Sound devices and the microphone level (sloth_center.sound), with pactl output as printed on a real machine."""
import array
import json
import sys
import tempfile
import types
import unittest
import wave
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

from sloth_center import sound  # noqa: E402

# pactl -f json: "description" was "(null)" on a real machine (2026-10-26); the names are in the properties
SINKS = [
    {"name": "alsa_output.pci-0000_01_00.1.hdmi-stereo", "description": "(null)", "mute": False,
     "properties": {"node.nick": "U34G3XM", "device.description": "GB206 High Definition Audio Controller"}},
    {"name": "alsa_output.usb-Turtle_Beach-00.analog-stereo", "description": "(null)", "mute": False,
     "properties": {"node.nick": "Stealth 600PC Gen 3"}},
]
SOURCES = [
    {"name": "alsa_output.pci-0000_01_00.1.hdmi-stereo.monitor", "description": "(null)", "mute": False,
     "properties": {}},
    {"name": "alsa_input.usb-046d_C922-02.analog-stereo", "description": "(null)", "mute": True,
     "properties": {"device.description": "C922 Pro Stream Webcam"}},
    {"name": "alsa_input.plain", "description": "Built-in Microphone", "mute": False, "properties": {}},
]


def run(cmd):
    if cmd[-1] == "sinks":
        return json.dumps(SINKS)
    if cmd[-1] == "sources":
        return json.dumps(SOURCES)
    if cmd[-1] == "get-default-sink":
        return SINKS[1]["name"] + "\n"
    return ""


class Devices(unittest.TestCase):
    def test_names_from_the_properties(self):
        self.assertEqual([d["label"] for d in sound.devices("sinks", run)], ["U34G3XM", "Stealth 600PC Gen 3"])

    def test_monitors_left_out_and_mute_read(self):
        sources = sound.devices("sources", run)
        self.assertEqual([d["label"] for d in sources], ["C922 Pro Stream Webcam", "Built-in Microphone"])
        self.assertEqual([d["muted"] for d in sources], [True, False])

    def test_default_and_broken_output(self):
        self.assertEqual(sound.default("sinks", run), SINKS[1]["name"])
        self.assertEqual(sound.devices("sinks", lambda cmd: "not json"), [])
        self.assertEqual(sound.devices("sinks", lambda cmd: ""), [])


class Level(unittest.TestCase):
    def wav(self, samples):
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        f.close()
        with wave.open(f.name, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(array.array("h", samples).tobytes())
        self.addCleanup(Path(f.name).unlink)
        return f.name

    def test_loud_and_quiet(self):
        self.assertEqual(sound.peak(self.wav([0, 120, -9000, 300])), 9000)
        self.assertLess(sound.peak(self.wav([3, -12, 40] * 1000)), sound.QUIET)

    def test_unreadable(self):
        self.assertEqual(sound.peak("/nonexistent.wav"), 0)


if __name__ == "__main__":
    unittest.main()
