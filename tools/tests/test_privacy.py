#!/usr/bin/env python3
"""Which apps can use the camera, the microphone and the location (sloth_center.privacy), from flatpak output."""
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6; reading the permissions is tested without it
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

from sloth_center import privacy  # noqa: E402

# As flatpak printed them on a real machine (2026-10-26)
DISCORD = """[Context]
shared=ipc;network;
sockets=pcsc;pulseaudio;wayland;x11;
devices=all;
filesystems=xdg-download;xdg-pictures:ro;xdg-run/pipewire-0;

[Session Bus Policy]
org.kde.StatusNotifierWatcher=talk
"""
EDITOR = """[Context]
shared=ipc;
sockets=wayland;
filesystems=!xdg-run/pipewire-0;home;
devices=dri;
"""
MAPS = """[Context]
sockets=wayland;
"""
PORTALS = {
    "com.discordapp.Discord": "notifications\tnotification\tcom.discordapp.Discord\tyes\t0x00\n",
    "org.example.Editor": "",
    "org.example.Maps": "location\tlocation\torg.example.Maps\tEXACT\t1700000000\n"
                        "devices\tcamera\torg.example.Maps\tyes\t0x00\n",
}
INFO = {"com.discordapp.Discord": DISCORD, "org.example.Editor": EDITOR, "org.example.Maps": MAPS}


def run(cmd):
    if cmd[:2] == ["flatpak", "list"]:
        return "org.example.Maps\tMaps\ncom.discordapp.Discord\tDiscord\norg.example.Editor\tEditor\n"
    if cmd[:2] == ["flatpak", "info"]:
        return INFO[cmd[-1]]
    if cmd[:2] == ["flatpak", "permission-show"]:
        return PORTALS[cmd[-1]]
    return ""


class Privacy(unittest.TestCase):
    def test_all_devices_and_sound(self):
        self.assertEqual(privacy.access("com.discordapp.Discord", run),
                         {"camera": True, "microphone": True, "location": False})

    def test_nothing_and_a_denied_pipewire(self):
        self.assertEqual(privacy.access("org.example.Editor", run),
                         {"camera": False, "microphone": False, "location": False})

    def test_portal_permissions(self):
        self.assertEqual(privacy.access("org.example.Maps", run),
                         {"camera": True, "microphone": False, "location": True})

    def test_location_turned_off_in_the_portal(self):
        original = PORTALS["org.example.Maps"]
        PORTALS["org.example.Maps"] = "location\tlocation\torg.example.Maps\tNONE\t0\n"
        try:
            self.assertFalse(privacy.access("org.example.Maps", run)["location"])
        finally:
            PORTALS["org.example.Maps"] = original

    def test_overview_by_name(self):
        result = privacy.overview(run)
        self.assertEqual([a["name"] for a in result["camera"]], ["Discord", "Maps"])
        self.assertEqual([a["name"] for a in result["microphone"]], ["Discord"])
        self.assertEqual([a["id"] for a in result["location"]], ["org.example.Maps"])

    def test_no_flatpak(self):
        self.assertEqual(privacy.overview(lambda cmd: ""), {"camera": [], "microphone": [], "location": []})


if __name__ == "__main__":
    unittest.main()
