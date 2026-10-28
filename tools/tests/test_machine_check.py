#!/usr/bin/env python3
"""The installer's first-page check (sloth_installer.system.machine_check) with made-up /sys and /proc."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "iso/files/usr/lib/sloth-os/sloth-installer"))

from sloth_installer import system  # noqa: E402


def write(path, text, binary=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text) if binary else path.write_text(text)


class MachineCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.firmware = self.root / "firmware/efi"
        self.firmware.mkdir(parents=True)
        self.pci = self.root / "pci"
        self.power = self.root / "power"
        self.meminfo = self.root / "meminfo"
        write(self.meminfo, "MemTotal:       16315480 kB\nMemFree:  100 kB\n")
        write(self.pci / "0000:00:02.0/vendor", "0x8086\n")
        write(self.pci / "0000:00:02.0/class", "0x030000\n")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return system.machine_check(self.firmware, self.pci, self.power, self.meminfo)

    def ids(self):
        return [(c["id"], c["level"]) for c in self.check()]

    def test_a_good_desktop(self):
        self.assertEqual(self.check(), [])

    def test_legacy_bios_blocks(self):
        self.firmware.rmdir()
        self.assertEqual(self.ids(), [("bios", "block")])

    def test_little_memory(self):
        write(self.meminfo, "MemTotal:        2000000 kB\n")
        self.assertEqual(self.ids(), [("memory", "warn")])
        write(self.meminfo, "MemTotal:        3900000 kB\n")   # a 4 GB computer: fine
        self.assertEqual(self.check(), [])

    def test_laptop_on_battery_and_plugged_in(self):
        write(self.power / "BAT0/type", "Battery\n")
        write(self.power / "AC/type", "Mains\n")
        write(self.power / "AC/online", "0\n")
        self.assertEqual(self.ids(), [("battery", "warn")])
        write(self.power / "AC/online", "1\n")
        self.assertEqual(self.check(), [])

    def test_a_mouse_battery_is_not_a_laptop(self):
        write(self.power / "hidpp_battery_0/type", "Battery\n")
        write(self.power / "hidpp_battery_0/scope", "Device\n")
        self.assertEqual(self.check(), [])

    def test_secure_boot_with_nvidia(self):
        write(self.firmware / system.SECURE_BOOT_VAR, b"\x06\x00\x00\x00\x01", binary=True)
        self.assertEqual(self.check(), [])   # Intel graphics only
        write(self.pci / "0000:01:00.0/vendor", "0x10de\n")
        write(self.pci / "0000:01:00.0/class", "0x030000\n")
        self.assertEqual(self.ids(), [("secureboot_nvidia", "info")])
        write(self.firmware / system.SECURE_BOOT_VAR, b"\x06\x00\x00\x00\x00", binary=True)
        self.assertEqual(self.check(), [])   # Secure Boot off

    def test_every_check_has_an_id_in_the_list(self):
        self.firmware.rmdir()
        write(self.meminfo, "MemTotal:        2000000 kB\n")
        self.assertTrue({c["id"] for c in self.check()} <= set(system.CHECKS))


if __name__ == "__main__":
    unittest.main()
