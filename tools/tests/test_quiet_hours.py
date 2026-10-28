#!/usr/bin/env python3
"""Quiet hours (sloth_common.quiet_hours): to the minute, over midnight, the time left, deferring a notification,
and reading the first version's whole hours."""
import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import quiet_hours as qh  # noqa: E402


def at(hour, minute=0):
    return datetime.datetime(2026, 10, 27, hour, minute)


def hm(hour, minute=0):
    return hour * 60 + minute


class QuietHours(unittest.TestCase):
    def test_over_midnight(self):
        cfg = {"enabled": True, "start": hm(22), "end": hm(7)}
        self.assertTrue(qh.is_quiet(cfg, at(23)))
        self.assertTrue(qh.is_quiet(cfg, at(3)))
        self.assertFalse(qh.is_quiet(cfg, at(7)))
        self.assertFalse(qh.is_quiet(cfg, at(12)))
        self.assertTrue(qh.is_quiet(cfg, at(22)))

    def test_to_the_minute(self):
        cfg = {"enabled": True, "start": hm(21, 30), "end": hm(7, 15)}
        self.assertFalse(qh.is_quiet(cfg, at(21, 29)))
        self.assertTrue(qh.is_quiet(cfg, at(21, 30)))
        self.assertTrue(qh.is_quiet(cfg, at(7, 14)))
        self.assertFalse(qh.is_quiet(cfg, at(7, 15)))
        self.assertEqual(qh.seconds_left(cfg, at(7)), 15 * 60)

    def test_within_a_day_and_off(self):
        cfg = {"enabled": True, "start": hm(18), "end": hm(23)}
        self.assertTrue(qh.is_quiet(cfg, at(20)))
        self.assertFalse(qh.is_quiet(cfg, at(23)))
        self.assertFalse(qh.is_quiet({**cfg, "enabled": False}, at(20)))
        self.assertFalse(qh.is_quiet({"enabled": True, "start": hm(5), "end": hm(5)}, at(5)))

    def test_time_left(self):
        cfg = {"enabled": True, "start": hm(22), "end": hm(7)}
        self.assertEqual(qh.seconds_left(cfg, at(23, 30)), 7.5 * 3600)
        self.assertEqual(qh.seconds_left(cfg, at(6)), 3600)

    def test_load_checks_the_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quiet-hours.json"
            self.assertEqual(qh.load(path), qh.DEFAULTS)
            path.write_text('{"enabled": true, "start": "25:00", "end": "6:30"}')
            self.assertEqual(qh.load(path), {"enabled": True, "start": hm(22), "end": hm(6, 30)})
            qh.save({"enabled": True, "start": hm(18, 45), "end": hm(23)}, path)
            self.assertEqual(json.loads(path.read_text()), {"enabled": True, "start": "18:45", "end": "23:00"})
            self.assertEqual(qh.load(path), {"enabled": True, "start": hm(18, 45), "end": hm(23)})

    def test_first_version_whole_hours(self):
        """The first version saved whole hours as numbers; a saved setting must not be lost."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quiet-hours.json"
            path.write_text('{"enabled": true, "start": 22, "end": 13}')
            self.assertEqual(qh.load(path), {"enabled": True, "start": hm(22), "end": hm(13)})
            path.write_text('{"enabled": true, "start": 99, "end": true}')
            self.assertEqual(qh.load(path), {"enabled": True, "start": hm(22), "end": hm(7)})

    def test_defer_sets_a_timer_only_in_the_quiet_hours(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quiet-hours.json"
            qh.save({"enabled": True, "start": hm(22), "end": hm(7)}, path)
            with mock.patch.object(qh.subprocess, "run") as run:
                self.assertFalse(qh.defer("sloth_center.update_notify", at(12), path))
                run.assert_not_called()
                self.assertTrue(qh.defer("sloth_center.update_notify", at(23), path))
                cmd = run.call_args[0][0]
                self.assertIn("--unit=sloth-quiet-update-notify", cmd)
                self.assertIn(f"--on-active={8 * 3600 + 60}", cmd)
                self.assertEqual(cmd[-3:], ["/usr/bin/python3", "-m", "sloth_center.update_notify"])


if __name__ == "__main__":
    unittest.main()
