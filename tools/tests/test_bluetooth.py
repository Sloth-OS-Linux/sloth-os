#!/usr/bin/env python3
"""Bluetooth (sloth_center.bluetooth.parse): adapter, power and the connected devices from busctl's JSON."""
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

from sloth_center import bluetooth  # noqa: E402


def v(kind, data):
    return {"type": kind, "data": data}


def managed(objects):
    """As `busctl --json=short call org.bluez / …GetManagedObjects` prints it."""
    return json.dumps({"type": "a{oa{sa{sv}}}", "data": [objects]})


OBJECTS = {
    "/org/bluez": {"org.bluez.AgentManager1": {}},
    "/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": v("b", True), "Name": v("s", "laptop")}},
    "/org/bluez/hci0/dev_AA": {
        "org.bluez.Device1": {"Alias": v("s", "Xbox Wireless Controller"), "Connected": v("b", True),
                              "Icon": v("s", "input-gaming")},
        "org.bluez.Battery1": {"Percentage": v("y", 64)},
    },
    "/org/bluez/hci0/dev_BB": {
        "org.bluez.Device1": {"Name": v("s", "Old Speaker"), "Connected": v("b", False), "Paired": v("b", True)},
    },
    "/org/bluez/hci0/dev_CC": {
        "org.bluez.Device1": {"Address": v("s", "CC:CC:CC:CC:CC:CC"), "Connected": v("b", True)},
    },
}


class Parse(unittest.TestCase):
    def test_adapter_and_connected_devices(self):
        r = bluetooth.parse(managed(OBJECTS))
        self.assertEqual((r["adapter"], r["adapterPath"], r["powered"]), (True, "/org/bluez/hci0", True))
        self.assertEqual([d["name"] for d in r["devices"]], ["Xbox Wireless Controller", "CC:CC:CC:CC:CC:CC"])
        self.assertEqual([d["battery"] for d in r["devices"]], [64, -1])
        self.assertEqual(r["devices"][1]["icon"], "preferences-system-bluetooth")

    def test_turned_off(self):
        objects = {"/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": v("b", False)}}}
        r = bluetooth.parse(managed(objects))
        self.assertEqual((r["adapter"], r["powered"], r["devices"]), (True, False, []))

    def test_no_bluetooth_at_all(self):
        # without an adapter the service does not start: busctl prints nothing
        self.assertEqual(bluetooth.parse(""), {"adapter": False, "adapterPath": "", "powered": False, "devices": []})
        self.assertFalse(bluetooth.parse(managed({"/org/bluez": {}}))["adapter"])


if __name__ == "__main__":
    unittest.main()
