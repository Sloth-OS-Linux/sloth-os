#!/usr/bin/env python3
"""What "Clean up" may delete (sloth_center.cleanup): old cache files, the Trash, used installers."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center/sloth_center"))

import cleanup  # noqa: E402  (no Qt in it)

DAY = 86400


def touch(path, age_days=0, data=b"x" * 5000):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    when = time.time() - age_days * DAY
    os.utime(path, (when, when))
    return path


class Cache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name) / "cache"
        self.old = touch(self.cache / "app/old.bin", age_days=40)
        self.new = touch(self.cache / "app/new.bin", age_days=2)
        self.ours = touch(self.cache / "sloth-os/apps/notepad/naplo/x.log", age_days=90)
        self.loose = touch(self.cache / "loose.tmp", age_days=60)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_old_files_and_not_ours(self):
        found = {p for p, _ in cleanup.old_cache_files(self.cache)}
        self.assertEqual(found, {str(self.old), str(self.loose)})

    def test_recently_read_counts_as_used(self):
        os.utime(self.old, (time.time(), time.time() - 40 * DAY))
        self.assertNotIn(str(self.old), {p for p, _ in cleanup.old_cache_files(self.cache)})

    def test_delete_and_empty_folders(self):
        touch(self.cache / "gone/deep/a.bin", age_days=40)
        cleanup.delete_files(cleanup.old_cache_files(self.cache))
        cleanup.remove_empty_dirs(self.cache)
        self.assertTrue(self.new.exists() and self.ours.exists())
        self.assertFalse(self.old.exists() or self.loose.exists())
        self.assertFalse((self.cache / "gone").exists())
        self.assertTrue((self.cache / "sloth-os").exists())

    def test_links_are_not_followed(self):
        outside = touch(Path(self.tmp.name) / "important/file.bin", age_days=100)
        (self.cache / "link").symlink_to(outside.parent)
        cleanup.delete_files(cleanup.old_cache_files(self.cache))
        self.assertTrue(outside.exists())


class Trash(unittest.TestCase):
    def test_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            trash = Path(tmp)
            touch(trash / "files/photo.jpg")
            touch(trash / "files/folder/doc.txt")
            touch(trash / "info/photo.jpg.trashinfo", data=b"[Trash Info]\n")
            self.assertGreater(cleanup.trash_size(trash), 0)
            self.assertGreater(cleanup.empty_trash(trash), 0)
            self.assertEqual(list((trash / "files").iterdir()) + list((trash / "info").iterdir()), [])
            self.assertEqual(cleanup.empty_trash(Path(tmp) / "missing"), 0)


class Installers(unittest.TestCase):
    def test_only_used_ones_in_the_home_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            used = touch(home / "Downloads/iview476_x64_setup.exe")
            inside = touch(home / "Applications/IrfanView/setup.exe")
            elsewhere = touch(Path(tempfile.gettempdir()) / f"sloth-test-{os.getpid()}.exe")
            try:
                found = cleanup.used_installers([str(used), str(used), str(inside), str(elsewhere), "",
                                                 str(home / "Downloads/deleted.exe")], home)
                self.assertEqual([p for p, _ in found], [str(used.resolve())])
            finally:
                elsewhere.unlink()


if __name__ == "__main__":
    unittest.main()
