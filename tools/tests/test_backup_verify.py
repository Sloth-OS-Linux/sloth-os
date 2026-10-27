#!/usr/bin/env python3
"""Reading back a saved state (sloth_common.snapshots.verify): counts, unreadable files, links, permissions."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import snapshots  # noqa: E402


class Verify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for i in range(12):
            (self.root / "Documents").mkdir(exist_ok=True)
            (self.root / "Documents" / f"note{i}.txt").write_text("hello " * i)

    def tearDown(self):
        for p in self.root.rglob("*"):
            if p.is_file() and not p.is_symlink():
                p.chmod(0o644)
        self.tmp.cleanup()

    def test_all_readable(self):
        self.assertEqual(snapshots.verify(self.root), (12, []))

    def test_sample_size(self):
        checked, bad = snapshots.verify(self.root, sample=5)
        self.assertEqual((checked, bad), (5, []))

    def test_links_are_not_followed(self):
        (self.root / "link").symlink_to("/nonexistent/file")
        self.assertEqual(snapshots.verify(self.root)[0], 12)

    @unittest.skipIf(os.geteuid() == 0, "root can read everything")
    def test_no_permission_is_not_a_fault(self):
        locked = self.root / "Documents" / "note3.txt"
        locked.chmod(0)
        self.assertEqual(snapshots.verify(self.root), (11, []))

    def test_empty(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(snapshots.verify(empty), (0, []))


if __name__ == "__main__":
    unittest.main()
