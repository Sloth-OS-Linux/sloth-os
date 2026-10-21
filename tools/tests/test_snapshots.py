#!/usr/bin/env python3
"""A test of the file backup (home-snapshots, sloth_common.snapshots, "Previous versions") on a real Btrfs.

It runs as root in the Sloth OS image (btrfs-progs, PySide6), with a Btrfs made on a loop device; instead of
/var/home it uses a folder on it. From Windows (WSL, podman; the btrfs module is needed: modprobe btrfs):
  wsl -d podman-machine-default -u root -- podman run --rm --privileged --cgroups=disabled \
      -v /mnt/c/Users/batho/sloth-os:/repo:ro --entrypoint python3 ghcr.io/sloth-os-linux/sloth-os:latest \
      /repo/tools/tests/test_snapshots.py
"""
import datetime
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import snapshots as snap  # noqa: E402


def load_script():
    path = REPO / "files/system/usr/libexec/sloth-os/home-snapshots"
    loader = SourceFileLoader("home_snapshots", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("home_snapshots", loader))
    loader.exec_module(module)
    return module


hs = load_script()
UID = 1000


def sh(*cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def write(path, text, uid=UID):
    """A file in the user's name (the parent folders created are theirs too)."""
    missing = [p for p in path.parents if not p.exists()]
    path.parent.mkdir(parents=True, exist_ok=True)
    for p in missing:
        os.chown(p, uid, uid)
    path.write_text(text)
    os.chown(path, uid, uid)


class SnapshotsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        img = cls.tmp / "disk.img"
        sh("truncate", "-s", "2G", str(img))
        sh("mkfs.btrfs", "-q", str(img))
        cls.mnt = cls.tmp / "mnt"
        cls.mnt.mkdir()
        sh("mount", "-o", "loop", str(img), str(cls.mnt))

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["umount", str(cls.mnt)])

    def setUp(self):
        root = self.mnt / f"var{self._testMethodName}"
        root.mkdir()
        snap.HOME_ROOT = root / "home"
        snap.SNAP_DIR = snap.HOME_ROOT / ".snapshots"
        snap.CONFIG = root / "snapshots.json"
        hs.MIN_FREE_BYTES = 0
        hs.MIN_FREE_RATIO = 0
        self.home = snap.HOME_ROOT / "alice"
        self.home.mkdir(parents=True)
        os.chown(self.home, UID, UID)
        os.chmod(self.home, 0o700)
        write(self.home / "Documents/résumé.txt", "first")
        write(self.home / ".cache/big.bin", "cache")
        write(self.home / ".var/app/org.mozilla.firefox/cache/x", "ffcache")
        write(self.home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/game.bin", "game")
        write(self.home / "Documents/sub/deep.txt", "deep")

    def test_layout_converts_and_keeps_data(self):
        self.assertEqual(snap.state(), "pending")
        self.assertEqual(hs.layout(), 0)
        self.assertEqual(snap.state(), "ready")
        steamapps = self.home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
        for p in (self.home / ".cache", self.home / ".var/app/org.mozilla.firefox/cache", steamapps):
            self.assertTrue(snap.is_subvolume(p), p)
        self.assertFalse(snap.is_subvolume(self.home))
        self.assertEqual((self.home / "Documents/résumé.txt").read_text(), "first")
        self.assertEqual((steamapps / "common/game.bin").read_text(), "game")
        st = os.stat(self.home)
        self.assertEqual((st.st_uid, st.st_mode & 0o777), (UID, 0o700))
        self.assertEqual(os.stat(self.home / ".cache").st_uid, UID)
        leftovers = [p for p in snap.HOME_ROOT.parent.rglob("*") if ".sloth-" in p.name]
        self.assertEqual(leftovers, [])
        # the second time there is nothing to do
        self.assertEqual(hs.layout(), 0)

    def test_layout_creates_missing_cache(self):
        sh("rm", "-rf", str(self.home / ".cache"))
        hs.layout()
        self.assertTrue(snap.is_subvolume(self.home / ".cache"))
        self.assertEqual(os.stat(self.home / ".cache").st_uid, UID)

    def test_recover_interrupted_swap(self):
        # interrupted during the two-step swap: the original under the name ".sloth-old", nothing in its place
        games = self.home / "Games"
        write(games / "a.txt", "game")
        old = hs.side(games, hs.OLD_SUFFIX)
        os.rename(games, old)
        new = hs.side(games, hs.NEW_SUFFIX)
        sh("btrfs", "subvolume", "create", str(new))
        hs.layout()
        self.assertTrue(snap.is_subvolume(games))
        self.assertEqual((games / "a.txt").read_text(), "game")
        self.assertFalse(os.path.lexists(old) or os.path.lexists(new))

    def test_take_versions_locate(self):
        hs.layout()
        self.assertTrue(hs.take(True)["ok"])
        doc = self.home / "Documents/résumé.txt"
        write(doc, "second, longer")
        # because of the names' one-second precision, the second snapshot comes one second later
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=2)
        name = snap.make_name(later)
        sh("btrfs", "subvolume", "snapshot", "-r", str(snap.HOME_ROOT), str(snap.SNAP_DIR / name))
        self.assertEqual(oct(os.stat(snap.SNAP_DIR).st_mode & 0o777), "0o755")
        rel, problem = snap.locate(doc)
        self.assertEqual((str(rel), problem), ("alice/Documents/résumé.txt", ""))
        found = snap.versions_of(rel)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0][2].read_text(), "second, longer")
        self.assertEqual(found[1][2].read_text(), "first")
        # the excluded folders are not in the snapshot
        self.assertEqual(list((snap.SNAP_DIR / name / "alice/.cache").iterdir()), [])
        self.assertEqual(snap.locate(self.home / ".cache/big.bin"), (None, "excluded"))
        self.assertEqual(snap.locate("/etc/hostname"), (None, "outside"))
        self.assertEqual(snap.locate(snap.SNAP_DIR / name / "alice"), (None, "outside"))

    def test_take_respects_interval_and_disabled(self):
        hs.layout()
        hs.take(False)
        self.assertEqual(len(snap.list_snapshots()), 1)
        hs.take(False)  # no new one within 50 minutes
        self.assertEqual(len(snap.list_snapshots()), 1)
        snap.CONFIG.write_text('{"enabled": false}')
        sh("btrfs", "subvolume", "delete", str(snap.SNAP_DIR / snap.list_snapshots()[0][0]))
        hs.take(False)
        self.assertEqual(snap.list_snapshots(), [])

    def test_low_space_keeps_newest_and_skips(self):
        hs.layout()
        hs.take(True)
        newest = snap.make_name(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=2))
        sh("btrfs", "subvolume", "snapshot", "-r", str(snap.HOME_ROOT), str(snap.SNAP_DIR / newest))
        hs.MIN_FREE_RATIO = 1.0  # never enough space
        result = hs.take(True)
        self.assertEqual(result, {"ok": False, "error": "no-space"})
        self.assertEqual([n for n, _t in snap.list_snapshots()], [newest])

    def test_delete_all(self):
        hs.layout()
        hs.take(True)
        hs.delete_all()
        self.assertEqual(snap.list_snapshots(), [])

    def test_restore_merge_and_copy(self):
        from PySide6.QtCore import QCoreApplication
        from sloth_center import versions as v
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_DATA_HOME"] = str(self.home / ".local/share")
        hs.layout()
        hs.take(True)
        old_docs = snap.SNAP_DIR / snap.list_snapshots()[0][0] / "alice/Documents"
        docs = self.home / "Documents"
        write(docs / "résumé.txt", "rewritten")
        write(docs / "new.txt", "new")
        os.unlink(docs / "sub/deep.txt")
        self.assertEqual(v.count_deleted(old_docs, docs), 1)
        # only the deleted ones
        self.assertEqual(v.merge(old_docs, docs, only_missing=True), (1, 0))
        self.assertEqual((docs / "sub/deep.txt").read_text(), "deep")
        self.assertEqual((docs / "résumé.txt").read_text(), "rewritten")
        # full restore: the changed one goes to the Trash, the new one stays
        self.assertEqual(v.merge(old_docs, docs, only_missing=False), (1, 0))
        self.assertEqual((docs / "résumé.txt").read_text(), "first")
        self.assertEqual((docs / "new.txt").read_text(), "new")
        trashed = list((self.home / ".local/share/Trash/files").iterdir())
        self.assertEqual([p.read_text() for p in trashed], ["rewritten"])
        # as a copy
        when = datetime.datetime(2026, 10, 19, 12, 0, tzinfo=datetime.timezone.utc)
        target = v.copy_name(docs / "résumé.txt", when)
        self.assertRegex(target.name, r"^résumé \(2026-10-19 \d\d\.00\)\.txt$")

    def test_to_keep(self):
        now = datetime.datetime(2026, 10, 20, 12, 0, tzinfo=datetime.timezone.utc)
        snaps = [(f"s{h}", now - datetime.timedelta(hours=h)) for h in range(0, 24 * 120, 1)]
        keep = snap.to_keep(snaps, 31, now)
        ages = sorted((now - t).total_seconds() / 3600 for n, t in snaps if n in keep)
        self.assertEqual(sum(1 for a in ages if a < 24), 24)               # every hour of the last day
        self.assertTrue(all(a <= 31 * 24 for a in ages))                   # nothing beyond the keep time
        self.assertLess(len(keep), 24 + 14 + 6)                            # one a day, then one a week
        self.assertIn("s0", snap.to_keep([("s0", now - datetime.timedelta(days=400))], 14, now))


if __name__ == "__main__":
    if os.geteuid() != 0:
        sys.exit("must be run as root (Btrfs loop device)")
    unittest.main(verbosity=2)
