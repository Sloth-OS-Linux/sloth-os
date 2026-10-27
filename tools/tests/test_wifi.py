#!/usr/bin/env python3
"""The Wi-Fi check (sloth_center.wifi.diagnose) with made-up nmcli / rfkill answers."""
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6; the check is tested without it
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.QTimer = None
    qtcore.Property = lambda *a, **k: (lambda f: f)  # as a decorator and as a plain call
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import wifi  # noqa: E402


def machine(devices="wifi:connected:wlp2s0\nethernet:unavailable:enp3s0\n", rfkill="wlan unblocked unblocked\n",
            radio="enabled\n", networks="no:Neighbour:80\nyes:Home\\:5G:72\n", connectivity="full\n"):
    # the most specific first: the network list command also has "device" in it
    answers = {
        "list": networks, "rfkill": rfkill, "radio": radio, "CONNECTIVITY": connectivity, "device": devices,
    }

    def run(cmd):
        for key, value in answers.items():
            if key in cmd:
                return value
        return None
    return run


def last(steps):
    return steps[-1]["id"], steps[-1]["state"], steps[-1]["action"]


class Diagnose(unittest.TestCase):
    def test_everything_works(self):
        steps = wifi.diagnose(machine())
        self.assertEqual([s["id"] for s in steps], ["adapter", "switch", "network", "signal", "internet"])
        self.assertTrue(all(s["state"] == wifi.OK for s in steps))
        self.assertIn("Home:5G", steps[2]["text"])  # a ":" in the network name
        self.assertIn("72", steps[3]["text"])

    def test_no_adapter(self):
        self.assertEqual(last(wifi.diagnose(machine(devices="ethernet:connected:enp3s0\nwifi-p2p:disconnected:p2p\n"))),
                         ("adapter", wifi.ERROR, "drivers"))

    def test_key_switched_off(self):
        self.assertEqual(last(wifi.diagnose(machine(rfkill="bluetooth unblocked unblocked\nwlan unblocked blocked\n"))),
                         ("switch", wifi.ERROR, ""))

    def test_turned_off_in_software(self):
        self.assertEqual(last(wifi.diagnose(machine(radio="disabled\n"))), ("switch", wifi.WARN, "turnOn"))
        self.assertEqual(last(wifi.diagnose(machine(rfkill="wlan blocked unblocked\n"))), ("switch", wifi.WARN, "turnOn"))

    def test_not_connected(self):
        self.assertEqual(last(wifi.diagnose(machine(devices="wifi:disconnected:wlp2s0\n"))),
                         ("network", wifi.WARN, "networks"))
        self.assertEqual(last(wifi.diagnose(machine(devices="wifi:unavailable:wlp2s0\n"))),
                         ("network", wifi.ERROR, "drivers"))

    def test_weak_signal_still_checks_the_internet(self):
        steps = wifi.diagnose(machine(networks="yes:Home:25\n"))
        self.assertEqual(steps[3]["state"], wifi.WARN)
        self.assertEqual(steps[-1]["id"], "internet")

    def test_sign_in_page_and_no_internet(self):
        self.assertEqual(last(wifi.diagnose(machine(connectivity="portal\n"))), ("internet", wifi.WARN, "portal"))
        self.assertEqual(last(wifi.diagnose(machine(connectivity="limited\n"))), ("internet", wifi.ERROR, ""))

    def test_nmcli_missing(self):
        self.assertEqual(last(wifi.diagnose(lambda cmd: None)), ("adapter", wifi.ERROR, "drivers"))


if __name__ == "__main__":
    unittest.main()
