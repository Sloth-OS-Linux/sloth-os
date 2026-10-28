#!/usr/bin/env python3
"""When the automatic update runs (sloth_common/update_time.py) and the helper's drop-in it reads; no Qt or root."""
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
TIMER = TMP / "uupd.timer"
CONF = TMP / "uupd.timer.d" / "50-sloth-time.conf"
UUPD_TIMER = """[Unit]
Description=Auto Update System Timer For Universal Blue

[Timer]
# Run daily at 4:00 AM
OnCalendar=*-*-* 04:00:00
Persistent=true
RandomizedDelaySec=15m
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
        TIMER.write_text(UUPD_TIMER)
        CONF.unlink(missing_ok=True)

    def hour(self):
        return update_time.update_hour(str(TIMER), str(CONF))

    def test_base_image_time(self):
        self.assertEqual(self.hour(), 4)

    def test_no_timer(self):
        self.assertEqual(update_time.update_hour(str(TMP / "missing.timer"), str(CONF)), -1)

    def test_helper_sets_and_resets(self):
        helper = load_helper()
        self.assertEqual(helper.update_time("21"), {"ok": True})
        text = CONF.read_text()
        self.assertIn("OnCalendar=\nOnCalendar=*-*-* 21:00:00", text)  # the base time is cleared first
        self.assertEqual(self.hour(), 21)
        helper.update_time("0")
        self.assertEqual(self.hour(), 0)
        helper.update_time("default")
        self.assertFalse(CONF.exists())
        self.assertEqual(self.hour(), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
