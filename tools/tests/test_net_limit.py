#!/usr/bin/env python3
"""The download speed limit (sloth_common.net_limit): the units, reading the setting, when it applies, which
connections get it, and the tc commands."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import net_limit as nl  # noqa: E402

NONE = {"kbit": 0, "unit": "MB", "value": 0, "when": "always"}


class NetLimit(unittest.TestCase):
    def test_units(self):
        self.assertEqual(nl.to_kbit(10, "MB"), 80000)
        self.assertEqual(nl.to_kbit(10, "Mbit"), 10000)
        self.assertEqual(nl.to_kbit(500, "KB"), 4000)
        self.assertEqual(nl.to_kbit(1.5, "MB"), 12000)
        self.assertEqual(nl.to_kbit(64, "kbit"), 64)
        for bad in [(63, "kbit"), (0, "MB"), (-5, "MB"), (2000, "MB"), (10, "GB"), (True, "MB"), ("10", "MB")]:
            self.assertEqual(nl.to_kbit(*bad), 0, bad)

    def test_load_checks_the_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "net-limit.json"
            self.assertEqual(nl.load(path), NONE)     # no file: no limit
            for text, expected in [
                    ('{"kbit": 80000, "unit": "MB", "when": "always"}',
                     {"kbit": 80000, "unit": "MB", "value": 10, "when": "always"}),
                    ('{"kbit": 4000, "unit": "KB", "when": "updates"}',
                     {"kbit": 4000, "unit": "KB", "value": 500, "when": "updates"}),
                    ('{"kbit": 12000, "unit": "MB"}', {"kbit": 12000, "unit": "MB", "value": 1.5, "when": "always"}),
                    ('{"kbit": 5000, "unit": "GB", "when": "never"}',
                     {"kbit": 5000, "unit": "MB", "value": 0.62, "when": "always"}),
                    ('{"kbit": 10, "unit": "kbit"}', {**NONE, "unit": "kbit"}),
                    ('{"kbit": true}', NONE), ('[10]', NONE), ("not json", NONE)]:
                path.write_text(text)
                self.assertEqual(nl.load(path), expected, text)

    def test_when_it_applies(self):
        off = {"kbit": 0, "when": "always"}
        always = {"kbit": 80000, "when": "always"}
        updates = {"kbit": 80000, "when": "updates"}
        self.assertFalse(nl.wanted(off, "update-start", nl.UPDATE_UNITS))
        self.assertTrue(nl.wanted(always, "apply", []))
        self.assertTrue(nl.wanted(always, "update-stop", [], "rpm-ostreed.service"))
        self.assertTrue(nl.wanted(updates, "update-start", []))
        self.assertFalse(nl.wanted(updates, "apply", []))
        self.assertTrue(nl.wanted(updates, "apply", ["flatpak-system-update.service"]))
        # the system update stopped, the app update still runs: the limit stays
        self.assertFalse(nl.wanted(updates, "update-stop", ["rpm-ostreed.service"], "rpm-ostreed.service"))
        self.assertTrue(nl.wanted(updates, "update-stop", ["rpm-ostreed.service", "flatpak-system-update.service"],
                                  "rpm-ostreed.service"))

    def test_default_devices(self):
        v4 = [{"dst": "default", "gateway": "192.168.1.1", "dev": "enp8s0"},
              {"dst": "default", "gateway": "192.168.0.1", "dev": "wlp3s0"}]
        v6 = [{"dst": "default", "dev": "enp8s0"}, {"dst": "default", "dev": "lo"}, "junk"]
        self.assertEqual(nl.default_devices(v4, v6), ["enp8s0", "wlp3s0"])
        self.assertEqual(nl.default_devices([], None), [])

    def test_commands(self):
        self.assertEqual(nl.police(80000), ["rate", "80000kbit", "burst", "2000000"])   # 10 MB/s: 0.2 s = 2 MB
        self.assertEqual(nl.police(64), ["rate", "64kbit", "burst", "16000"])
        add_qdisc, add_filter = nl.on_commands("enp8s0", 80000)
        self.assertEqual(add_qdisc, ["tc", "qdisc", "add", "dev", "enp8s0", "handle", "ffff:", "ingress"])
        self.assertEqual(add_filter[-6:], ["police", "rate", "80000kbit", "burst", "2000000", "drop"])
        self.assertEqual(nl.off_command("enp8s0"), ["tc", "qdisc", "del", "dev", "enp8s0", "ingress"])


if __name__ == "__main__":
    unittest.main()
