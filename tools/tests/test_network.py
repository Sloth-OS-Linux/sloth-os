#!/usr/bin/env python3
"""Sloth Center's Wi-Fi page (sloth_center/network.py): what is read from nmcli's output."""
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

from sloth_center import network  # noqa: E402

LIST = """ :Neighbour 5G:42:WPA2
*:Home\\:Net:81:WPA2 WPA3
 :Home\\:Net:90:WPA2 WPA3
 :Cafe:65:
 ::30:WPA2
 :Office:55:WPA2 802.1X
 :Old:20:WEP
"""


class Network(unittest.TestCase):
    def test_terse_escapes(self):
        self.assertEqual(network.split_terse("*:Home\\:Net:81:WPA2"), ["*", "Home:Net", "81", "WPA2"])
        self.assertEqual(network.split_terse("a\\\\b:c"), ["a\\b", "c"])

    def test_networks(self):
        nets = network.parse_networks(LIST, saved={"Cafe"})
        names = [n["ssid"] for n in nets]
        self.assertEqual(names, ["Home:Net", "Cafe", "Office", "Neighbour 5G", "Old"])  # connected, saved, signal
        home = nets[0]
        self.assertTrue(home["connected"])
        self.assertEqual(home["kind"], "personal")
        self.assertEqual({n["ssid"]: n["kind"] for n in nets}["Cafe"], "open")
        self.assertEqual({n["ssid"]: n["kind"] for n in nets}["Office"], "enterprise")
        self.assertEqual({n["ssid"]: n["kind"] for n in nets}["Old"], "enterprise")  # WEP: KDE's window
        self.assertNotIn("", names)  # a hidden network is left out

    def test_devices_and_saved(self):
        devices = network.parse_devices("enp0s2:ethernet:connected:Wired connection 1\nwlan0:wifi:disconnected:\n"
                                        "lo:loopback:connected (externally):lo\n")
        self.assertEqual(devices["wifi"][0]["device"], "wlan0")
        self.assertEqual(devices["ethernet"][0]["state"], "connected")
        self.assertEqual(network.parse_saved("Home:802-11-wireless\nWired connection 1:802-3-ethernet\n"), {"Home"})

    def test_signal_icon(self):
        self.assertEqual(network.signal_icon(90), "network-wireless-signal-excellent")
        self.assertEqual(network.signal_icon(10), "network-wireless-signal-low")


if __name__ == "__main__":
    unittest.main()
