#!/usr/bin/env python3
"""When the automatic system update runs (sloth_common/update_time.py) and the helper's drop-in it reads; no Qt or
root. The timer files are copied from the image (2026-10-28): rpm-ostreed-automatic.timer and Universal Blue's
override.conf."""
import importlib.machinery
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import update_time  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="sloth-update-time-"))
TIMER = TMP / "rpm-ostreed-automatic.timer"
VENDOR = TMP / "rpm-ostreed-automatic.timer.d" / "override.conf"
CONF = TMP / "etc" / "rpm-ostreed-automatic.timer.d" / "zz-sloth-time.conf"
BASE_TIMER = """[Unit]
Description=rpm-ostree Automatic Update Trigger
ConditionPathExists=/run/ostree-booted

[Timer]
OnBootSec=1h
OnUnitInactiveSec=1d
Persistent=true

[Install]
WantedBy=timers.target
"""
UBLUE_OVERRIDE = """[Timer]
RandomizedDelaySec=10m
OnCalendar=*-*-* 4:00:00
Persistent=true
"""


def load_helper():
    """sloth-helper is a script without .py: loaded as a module, its update_time() writing under TMP."""
    path = str(REPO / "files/system/usr/libexec/sloth-os/sloth-helper")
    spec = importlib.util.spec_from_loader("sloth_helper", importlib.machinery.SourceFileLoader("sloth_helper", path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.UPDATE_TIME_CONF = str(CONF)
    module.run = lambda cmd, **kw: None  # no systemctl here
    return module


class UpdateTimeTest(unittest.TestCase):
    def setUp(self):
        TIMER.write_text(BASE_TIMER)
        VENDOR.parent.mkdir(parents=True, exist_ok=True)
        VENDOR.write_text(UBLUE_OVERRIDE)
        CONF.unlink(missing_ok=True)

    def hour(self):
        return update_time.update_hour(str(TIMER), str(CONF))

    def test_base_image_time(self):
        """Universal Blue's override.conf: daily at 4:00 (written "4:00:00", one digit)."""
        self.assertEqual(self.hour(), 4)

    def test_no_timer(self):
        self.assertEqual(update_time.update_hour(str(TMP / "missing.timer"), str(CONF)), -1)

    def test_helper_sets_only_our_hour(self):
        helper = load_helper()
        self.assertEqual(helper.update_time("21"), {"ok": True})
        text = CONF.read_text()
        # the base image's triggers are cleared (an hour after start, a day after the last run, 4:00), then ours
        for line in ("OnBootSec=\n", "OnUnitInactiveSec=\n", "OnCalendar=\nOnCalendar=*-*-* 21:00:00\n"):
            self.assertIn(line, text)
        self.assertEqual(self.hour(), 21)
        helper.update_time("0")
        self.assertEqual(self.hour(), 0)
        helper.update_time("default")
        self.assertFalse(CONF.exists())
        self.assertEqual(self.hour(), 4)

    def test_helper_writes_where_the_reader_looks(self):
        helper = importlib.util.module_from_spec(importlib.util.spec_from_loader(
            "h", importlib.machinery.SourceFileLoader("h", str(REPO / "files/system/usr/libexec/sloth-os/sloth-helper"))))
        helper.__spec__.loader.exec_module(helper)
        self.assertEqual(helper.UPDATE_TIME_CONF, update_time.UPDATE_TIME_CONF)
        self.assertTrue(update_time.UPDATE_TIMER.endswith("/" + helper.UPDATE_TIMER_UNIT))


if __name__ == "__main__":
    unittest.main(verbosity=2)
