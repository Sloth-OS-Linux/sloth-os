#!/usr/bin/env python3
"""Restore points: root's part (files/system/usr/libexec/sloth-os/restore-points: the system version kept, the
points' life), the user's part (sloth_center/restore_points.py: the list, the settings back at sign-in) and the
hourly backup keeping the points' snapshots. No root, Btrfs or ostree needed (the real snapshot is in
test_snapshots.py)."""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_common import snapshots as snap  # noqa: E402


def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


rpoints = load_script("restore_points_root", REPO / "files/system/usr/libexec/sloth-os/restore-points")
UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 11, 19, 12, 0, tzinfo=UTC)


def deploys(*specs):
    """("abc", booted, pinned)… -> rpm-ostree's list"""
    return [{"index": i, "checksum": c, "booted": b, "pinned": p} for i, (c, b, p) in enumerate(specs)]


class RootTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sloth-rp-"))
        self.state = self.tmp / "restore-points.json"
        self.pins = []
        patcher = mock.patch.object(rpoints, "ostree_pin", side_effect=lambda i, unpin=False: self.pins.append(
            ("unpin" if unpin else "pin", i)) or True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def create(self, reason, when, d, snapshot="snap"):
        return rpoints.create(reason, 1000, deploys=d, snapshot=snapshot, when=when, path=self.state)

    def test_pins_the_running_version_and_records_the_point(self):
        d = deploys(("new", True, False), ("old", False, False))
        p = self.create("driver", T0, d, "2026-11-19_12-00-00")
        self.assertEqual(self.pins, [("pin", 0)])
        saved = rpoints.load(self.state)
        self.assertEqual(len(saved), 1)
        self.assertEqual((saved[0]["reason"], saved[0]["checksum"], saved[0]["snapshot"], saved[0]["uid"]),
                         ("driver", "new", "2026-11-19_12-00-00", 1000))
        self.assertFalse(saved[0]["pinned_before"])
        self.assertEqual(p["id"], "20261119120000")
        self.assertEqual(oct(os.stat(self.state).st_mode & 0o777), "0o644")
        self.assertEqual(rpoints.protected(self.state), {"2026-11-19_12-00-00"})

    def test_same_change_within_a_minute_makes_one_point(self):
        d = deploys(("new", True, False))
        a = self.create("layout", T0, d)
        b = self.create("layout", T0 + datetime.timedelta(seconds=20), d)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(rpoints.load(self.state)), 1)
        self.create("layout", T0 + datetime.timedelta(minutes=5), d)
        self.assertEqual(len(rpoints.load(self.state)), 2)

    def test_a_version_the_user_kept_stays_kept(self):
        d = deploys(("kept", True, True))
        self.create("manual", T0, d)
        self.assertEqual(self.pins, [])                 # already pinned: nothing to do
        point = rpoints.load(self.state)[0]
        self.assertTrue(point["pinned_before"])
        with mock.patch.object(rpoints, "deployments", return_value=deploys(("kept", True, True))):
            rpoints.delete(point["id"], path=self.state)
        self.assertEqual(self.pins, [])                 # and it is not unpinned when the point goes
        self.assertEqual(rpoints.load(self.state), [])

    def test_at_most_five_and_thirty_days(self):
        # six points on six different versions, one a day: the oldest goes and its version is unpinned
        for day in range(6):
            d = deploys((f"v{day}", True, False), *[(f"v{k}", False, True) for k in range(day)])
            self.create("manual", T0 + datetime.timedelta(days=day), d)
        points = rpoints.load(self.state)
        self.assertEqual([p["checksum"] for p in points], ["v5", "v4", "v3", "v2", "v1"])
        self.assertIn(("unpin", 1), self.pins)          # v0 was at index 1 in the last list (after the booted one)
        # 31 days later every point is too old except the new one
        later = T0 + datetime.timedelta(days=37)
        d = deploys(("v9", True, False), *[(f"v{k}", False, True) for k in range(6)])
        released = self.create("manual", later, d)["released"]
        self.assertEqual(len(released), 5)
        self.assertEqual([p["checksum"] for p in rpoints.load(self.state)], ["v9"])

    def test_a_version_two_points_share_is_kept_while_one_lives(self):
        d = deploys(("same", True, False))
        first = self.create("layout", T0, d)
        self.create("driver", T0 + datetime.timedelta(minutes=5), d)
        self.pins.clear()
        with mock.patch.object(rpoints, "deployments", return_value=deploys(("same", True, True))):
            rpoints.delete(first["id"], path=self.state)
        self.assertEqual(self.pins, [])                 # the other point still needs it

    def test_unknown_reason_and_id_refused(self):
        with mock.patch.object(rpoints.os, "geteuid", return_value=0):
            self.assertEqual(rpoints.main(["create", "rm -rf"]), 2)
            self.assertEqual(rpoints.main(["delete", "../x"]), 2)


class HourlyBackupKeepsThem(unittest.TestCase):
    def test_protected_snapshots_are_not_pruned(self):
        tmp = Path(tempfile.mkdtemp(prefix="sloth-rp-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        state = tmp / "rp.json"
        state.write_text(json.dumps({"points": [{"id": "1", "snapshot": "2026-10-01_08-00-00"}]}))
        hs = load_script("home_snapshots", REPO / "files/system/usr/libexec/sloth-os/home-snapshots")
        old = [("2026-10-01_08-00-00", datetime.datetime(2026, 10, 1, 8, tzinfo=UTC)),
               ("2026-10-02_08-00-00", datetime.datetime(2026, 10, 2, 8, tzinfo=UTC)),
               ("2026-11-19_08-00-00", datetime.datetime(2026, 11, 19, 8, tzinfo=UTC))]
        deleted = []
        with mock.patch.object(snap, "RESTORE_POINTS", state), \
                mock.patch.object(hs.snap, "list_snapshots", return_value=old), \
                mock.patch.object(hs, "delete", side_effect=deleted.extend):
            hs.prune({"keep": "2w", "enabled": True})
        self.assertNotIn("2026-10-01_08-00-00", deleted)    # a restore point's
        self.assertIn("2026-10-02_08-00-00", deleted)       # too old, nobody keeps it


class SettingsBack(unittest.TestCase):
    def setUp(self):
        from sloth_center import restore_points as rp
        self.rp = rp
        self.tmp = Path(tempfile.mkdtemp(prefix="sloth-rp-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home" / "anna"
        self.snapdir = self.tmp / "home" / ".snapshots"
        old = self.snapdir / "2026-11-19_12-00-00" / "anna"
        for rel, text in ((".config/kdeglobals", "old colors"), (".config/plasma-org.kde.plasma.desktop-appletsrc",
                                                                   "old panels"),
                          (".local/share/plasma/look.txt", "old look"), ("Documents/letter.odt", "old letter")):
            (old / rel).parent.mkdir(parents=True, exist_ok=True)
            (old / rel).write_text(text)
        for rel, text in ((".config/kdeglobals", "new colors"), (".config/newapprc", "new app"),
                          (".local/share/kwin/scripts.txt", "new kwin"), ("Documents/letter.odt", "new letter")):
            (self.home / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.home / rel).write_text(text)
        mock.patch.object(rp, "PENDING", self.tmp / "state/restore-settings.json").start()
        mock.patch.object(rp, "ASIDE", self.home / ".local/share/sloth-os/before-restore").start()
        mock.patch.object(snap, "SNAP_DIR", self.snapdir).start()
        mock.patch.object(rp, "own_home_rel", return_value=Path("anna")).start()
        self.addCleanup(mock.patch.stopall)
        self.point = {"id": "20261119120000", "snapshot": "2026-11-19_12-00-00", "checksum": "abc",
                      "when": "2026-11-19T12:00:00+00:00", "reason": "layout"}

    def test_describe(self):
        rows = self.rp.describe([self.point, dict(self.point, id="2", snapshot="", checksum="gone-one")], "abc",
                                ["abc", "older"])
        self.assertEqual([(r["system"], r["settings"]) for r in rows], [("same", True), ("gone", False)])

    def test_back_at_sign_in_files_untouched_current_aside(self):
        self.assertTrue(self.rp.schedule_settings(self.point))
        restored, failed = self.rp.apply_pending(home=self.home, now=datetime.datetime(2026, 11, 20, 9, 0))
        self.assertEqual((restored, failed), (2, 0))       # .config and .local/share/plasma
        self.assertEqual((self.home / ".config/kdeglobals").read_text(), "old colors")
        self.assertEqual((self.home / ".config/plasma-org.kde.plasma.desktop-appletsrc").read_text(), "old panels")
        self.assertFalse((self.home / ".config/newapprc").exists())
        self.assertEqual((self.home / ".local/share/plasma/look.txt").read_text(), "old look")
        self.assertEqual((self.home / ".local/share/kwin/scripts.txt").read_text(), "new kwin")   # not in the point
        self.assertEqual((self.home / "Documents/letter.odt").read_text(), "new letter")         # files untouched
        aside = self.home / ".local/share/sloth-os/before-restore/2026-11-20 09.00.00"
        self.assertEqual((aside / ".config/kdeglobals").read_text(), "new colors")
        self.assertEqual((aside / ".config/newapprc").read_text(), "new app")
        self.assertIsNone(self.rp.pending())                # once only
        self.assertEqual(self.rp.apply_pending(home=self.home), (0, 0))

    def test_a_failed_copy_puts_the_current_settings_back(self):
        self.rp.schedule_settings(self.point)
        with mock.patch.object(self.rp, "_copy", return_value=False):
            restored, failed = self.rp.apply_pending(home=self.home)
        self.assertEqual((restored, failed), (0, 2))
        self.assertEqual((self.home / ".config/kdeglobals").read_text(), "new colors")
        self.assertEqual((self.home / ".config/newapprc").read_text(), "new app")

    def test_no_settings_in_the_point(self):
        self.assertFalse(self.rp.schedule_settings(dict(self.point, snapshot="")))
        self.assertIsNone(self.rp.pending())


if __name__ == "__main__":
    unittest.main()
