#!/usr/bin/env python3
"""Sloth Center's firmware updates (sloth_center/firmware.py): which releases are offered (only signed upgrades from
the stable LVFS) and when installing is held back (power). The JSON is the shape fwupd 2.1.9's
`fwupdmgr get-updates --json` gives (checked with its fwupd-tests fake webcam, which also installed end to end).
Needs PySide6 (the controller is a QObject); no fwupd needed."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import firmware as fw  # noqa: E402


def release(version, flags=("trusted-payload", "trusted-metadata", "is-upgrade"), remote="lvfs"):
    return {"RemoteId": remote, "Version": version, "Summary": "BIOS", "Urgency": "high",
            "Description": "<p>Fixes:</p><ul><li>sleep</li><li>fans</li></ul>", "Flags": list(flags)}


def device(releases, flags=("updatable", "internal", "needs-reboot", "require-ac", "affects-fde"), problems=()):
    return {"Name": "System Firmware", "DeviceId": "abc", "Vendor": "HP", "Version": "1.10",
            "Flags": list(flags), "Releases": releases, "Problems": list(problems)}


class Parse(unittest.TestCase):
    def test_signed_upgrade(self):
        [u] = fw.parse_updates({"Devices": [device([release("1.12"), release("1.11")])]})
        self.assertEqual((u["id"], u["current"], u["version"]), ("abc", "1.10", "1.12"))
        self.assertTrue(u["reboot"] and u["fde"] and u["ac"])
        self.assertEqual(u["notes"], "Fixes:\n• sleep\n• fans")

    def test_never_unsigned_older_or_testing(self):
        for r in (release("1.12", flags=("is-upgrade",)),                       # not signed
                  release("1.09", flags=("trusted-payload", "is-downgrade")),   # older
                  release("1.12", remote="lvfs-testing")):                     # the testing remote
            self.assertEqual(fw.parse_updates({"Devices": [device([r])]}), [], r)

    def test_not_updatable_now(self):
        self.assertEqual(fw.parse_updates({"Devices": [device([release("1.12")], flags=("updatable-hidden",))]}), [])

    def test_problems_kept(self):
        [u] = fw.parse_updates({"Devices": [device([release("1.12")], problems=("lid-is-closed", "other-thing"))]})
        self.assertEqual(u["problems"], ["lid-is-closed"])


class Power(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(fw, "POWER_SUPPLY", self.tmp)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.tmp)

    def supply(self, name, **values):
        (self.tmp / name).mkdir()
        for k, v in values.items():
            (self.tmp / name / k).write_text(v + "\n")

    def test_desktop(self):
        self.assertEqual(fw.power(), {"battery": False, "ac": True, "percent": None})

    def test_laptop(self):
        self.supply("AC", type="Mains", online="0")
        self.supply("BAT0", type="Battery", capacity="25")
        self.supply("hidpp_battery_0", type="Battery", capacity="5", scope="Device")   # a wireless mouse
        self.assertEqual(fw.power(), {"battery": True, "ac": False, "percent": 25})

    def test_blockers(self):
        self.supply("AC", type="Mains", online="1")
        self.supply("BAT0", type="Battery", capacity="20")
        ctl = fw.FirmwareController()
        ctl._updates = fw.parse_updates({"Devices": [device([release("1.12")])]})
        [u] = ctl.updates
        self.assertEqual(len(u["blockers"]), 1)          # plugged in, but under 30%
        self.assertTrue(u["recoveryKey"] and u["urgent"])
        (self.tmp / "BAT0/capacity").write_text("80\n")
        self.assertEqual(ctl.updates[0]["blockers"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
