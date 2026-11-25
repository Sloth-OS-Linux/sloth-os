#!/usr/bin/env python3
"""Driver options (sloth_common/driver_options.py, sloth-helper driver-options): the known fixes offered only for
drivers in use, the checks (a real driver, its real options, never one the computer needs to start), and the
modprobe.d file. A fake modinfo and a fake /sys/module."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="sloth-drivers-"))
os.environ.update(SLOTH_DRIVER_OPTIONS=str(TMP / "etc/driver-options.json"),
                  SLOTH_DRIVER_CONF=str(TMP / "etc/modprobe.d/sloth-user.conf"),
                  SLOTH_SYS_MODULE=str(TMP / "sys/module"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import driver_options as d  # noqa: E402

# a fake modinfo: these drivers exist, with these parameters
FAKE = TMP / "bin/modinfo"
FAKE.parent.mkdir(parents=True)
FAKE.write_text("""#!/bin/sh
case "$2" in
  rtl8188ee) printf 'ips:Using no link power save (default 1 is open)\\nfwlps:Set to 1 to use FW control power save\\n' ;;
  rtw88_pci) printf 'disable_aspm:Set Y to disable PCI ASPM support (bool)\\n' ;;
  nouveau) printf 'modeset:enable driver\\n' ;;
  nvme) printf 'io_queue_depth:set io queue depth\\n' ;;
  *) echo "modinfo: ERROR: Module $2 not found." >&2; exit 1 ;;
esac
""")
FAKE.chmod(0o755)
os.environ["PATH"] = f"{FAKE.parent}:{os.environ['PATH']}"


def load(name, path):
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DriverOptions(unittest.TestCase):
    def setUp(self):
        for p in (d.STATE, d.CONF):
            if p.exists():
                p.unlink()

    def test_known_fixes_only_for_drivers_in_use(self):
        self.assertEqual(d.suggestions([]), [])                     # nothing loaded: nothing offered
        (d.SYS_MODULE / "rtl8188ee").mkdir(parents=True)
        s = d.suggestions([])
        self.assertEqual([(x["id"], x["module"], x["options"]) for x in s],
                         [("realtek-wifi-power", "rtl8188ee", {"ips": "0", "fwlps": "0"})])
        # once applied, it is not offered again
        self.assertEqual(d.suggestions([{"module": "rtl8188ee", "options": {"ips": "0"}}]), [])
        self.assertEqual(d.fix_entry("realtek-wifi-power", "rtl8188ee"),
                         {"module": "rtl8188ee", "options": {"ips": "0", "fwlps": "0"}, "off": False,
                          "fix": "realtek-wifi-power"})
        self.assertIsNone(d.fix_entry("realtek-wifi-power", "nvme"))   # not one of its drivers

    def test_parse_and_check(self):
        self.assertEqual(d.parse_options("ips=0  fwlps=0"), {"ips": "0", "fwlps": "0"})
        for bad in ("ips", "ips=0; rm -rf /", "IPS=0", "", "a=$(x)"):
            self.assertIsNone(d.parse_options(bad), bad)
        self.assertIsNone(d.check([{"module": "rtl8188ee", "options": {"ips": "0", "fwlps": "0"}}]))
        self.assertEqual(d.check([{"module": "rtl8188ee", "options": {"nosuch": "1"}}]), "param")
        self.assertEqual(d.check([{"module": "nosuchdriver", "options": {"x": "1"}}]), "module")
        self.assertEqual(d.check([{"module": "rtl8188ee", "options": {}}]), "empty")
        self.assertEqual(d.check([{"module": "../etc", "options": {"x": "1"}}]), "module")
        # turning off: a real driver, never one the computer needs to start
        self.assertIsNone(d.check([{"module": "nouveau", "off": True}]))
        self.assertEqual(d.check([{"module": "nvme", "off": True}]), "protected")
        self.assertEqual(d.check([{"module": "nosuchdriver", "off": True}]), "module")

    def test_render(self):
        text = d.render([{"module": "rtl8188ee", "options": {"ips": "0", "fwlps": "0"}},
                         {"module": "nouveau", "off": True}])
        self.assertIn("options rtl8188ee fwlps=0 ips=0\n", text)
        self.assertIn("blacklist nouveau\n", text)
        self.assertTrue(text.startswith("# Sloth OS"))

    def test_the_helper_writes_both_files(self):
        helper = load("sloth_helper", REPO / "files/system/usr/libexec/sloth-os/sloth-helper")
        helper.sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
        ok = helper.driver_options({"entries": [{"module": "rtl8188ee", "options": {"ips": "0", "fwlps": "0"},
                                                 "fix": "realtek-wifi-power"}]})
        self.assertEqual(ok, {"ok": True})
        self.assertEqual(d.CONF.read_text().splitlines()[-1], "options rtl8188ee fwlps=0 ips=0")
        self.assertEqual(d.load()[0]["module"], "rtl8188ee")
        # a bad entry changes nothing
        self.assertEqual(helper.driver_options({"entries": [{"module": "nvme", "off": True}]}),
                         {"ok": False, "error": "protected"})
        self.assertIn("rtl8188ee", d.CONF.read_text())
        self.assertEqual(helper.driver_options({"entries": "x"}), {"ok": False, "error": "bad request"})
        # all removed: the modprobe file goes
        self.assertEqual(helper.driver_options({"entries": []}), {"ok": True})
        self.assertFalse(d.CONF.exists())
        self.assertEqual(json.loads(d.STATE.read_text()), {"entries": []})


if __name__ == "__main__":
    unittest.main()
