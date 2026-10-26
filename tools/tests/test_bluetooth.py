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
    qtcore.QTimer = None
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


class Read(unittest.TestCase):
    def run_with(self, rfkill):
        return lambda cmd: rfkill if cmd[0] == "rfkill" else managed(OBJECTS)

    def test_on(self):
        r = bluetooth.read(self.run_with("wlan unblocked unblocked\nbluetooth unblocked unblocked\n"))
        self.assertTrue(r["powered"])
        self.assertEqual(len(r["devices"]), 2)

    def test_turned_off_in_the_tray(self):
        # KDE's applet blocks it with rfkill; BlueZ may still say Powered for a moment
        r = bluetooth.read(self.run_with("bluetooth blocked unblocked\n"))
        self.assertEqual((r["adapter"], r["powered"], r["devices"]), (True, False, []))
        self.assertTrue(bluetooth.blocked(lambda cmd: "bluetooth unblocked blocked\n"))


class TurnOn(unittest.TestCase):
    def machine(self, wakes_after):
        """Blocked and off; after the block is lifted the adapter refuses Powered `wakes_after` times."""
        state = {"blocked": True, "powered": False, "refused": 0, "calls": []}

        def run(cmd):
            state["calls"].append(cmd[:2] if cmd[0] == "rfkill" else cmd[-4:])
            if cmd[:2] == ["rfkill", "unblock"]:
                state["blocked"] = False
            elif cmd[0] == "rfkill":
                return f"bluetooth {'blocked' if state['blocked'] else 'unblocked'} unblocked\n"
            elif "set-property" in cmd and not state["blocked"]:
                if state["refused"] < wakes_after:
                    state["refused"] += 1
                else:
                    state["powered"] = True
            elif "GetManagedObjects" in cmd:
                return managed({"/org/bluez/hci0": {"org.bluez.Adapter1": {"Powered": v("b", state["powered"])}}})
            return ""
        return run, state

    def test_waits_for_the_adapter(self):
        run, state = self.machine(wakes_after=2)
        result = bluetooth.turn_on("/org/bluez/hci0", run, wait=0)
        self.assertTrue(result["powered"])
        self.assertEqual(state["calls"][0], ["rfkill", "unblock"])

    def test_gives_up(self):
        run, _ = self.machine(wakes_after=99)
        self.assertFalse(bluetooth.turn_on("/org/bluez/hci0", run, wait=0, tries=3)["powered"])


if __name__ == "__main__":
    unittest.main()
