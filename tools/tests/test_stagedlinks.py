#!/usr/bin/env python3
"""Filling in the EA app's version switch (a link to the versioned folder): sloth_exe.stagedlinks.

It runs on Linux, without Qt and Wine:
  wsl -d podman-machine-default -- python3 -I /mnt/c/Users/batho/sloth-os/tools/tests/test_stagedlinks.py
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# loaded without the package's __init__ (that would pull in the Qt parts too)
_spec = importlib.util.spec_from_file_location(
    "stagedlinks", REPO / "files/system/usr/lib/sloth-os/sloth-exe/sloth_exe/stagedlinks.py")
stagedlinks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stagedlinks)


class StagedLinksTest(unittest.TestCase):
    def setUp(self):
        self.prefix = Path(tempfile.mkdtemp())
        self.base = self.prefix / "drive_c/Program Files/Electronic Arts/EA Desktop"
        self.active = self.base / "EA Desktop"

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def stage(self, version):
        d = self.base / version / "EA Desktop"
        d.mkdir(parents=True)
        (d / "EABackgroundService.exe").write_text(version)
        return d

    def test_applies(self):
        self.assertTrue(stagedlinks.applies(self.prefix, "EAappInstaller.exe"))
        self.assertFalse(stagedlinks.applies(self.prefix, "Battle.net-Setup.exe"))
        self.base.mkdir(parents=True)
        self.assertTrue(stagedlinks.applies(self.prefix, "game.exe"))

    def test_link_after_install_rename(self):
        self.stage("13.809.0.6322")
        self.assertTrue(stagedlinks.fix(self.prefix))
        self.assertEqual(os.readlink(self.active), "13.809.0.6322/EA Desktop")
        self.assertEqual((self.active / "EABackgroundService.exe").read_text(), "13.809.0.6322")
        self.assertFalse(stagedlinks.fix(self.prefix))  # the second time there is nothing to do

    def test_update_moves_link_to_newest(self):
        self.stage("13.809.0.6322")
        stagedlinks.fix(self.prefix)
        self.stage("13.900.1.7000-1770576199")
        self.stage("13.95.0.1")  # older, only "bigger" as text
        stagedlinks.fix(self.prefix)
        self.assertEqual(os.readlink(self.active), "13.900.1.7000-1770576199/EA Desktop")

    def test_real_folder_untouched(self):
        self.stage("13.809.0.6322")
        self.active.mkdir()
        self.assertFalse(stagedlinks.fix(self.prefix))
        self.assertFalse(self.active.is_symlink())

    def test_watcher_is_fast_enough(self):
        """Like the installer: the files into the active folder, then a rename to the versioned place; the service
        looks for the file a few milliseconds later."""
        found = {}

        def installer():
            time.sleep(0.2)
            self.active.mkdir(parents=True)
            (self.active / "EABackgroundService.exe").write_text("x")
            time.sleep(0.3)  # with the real installer the copy takes seconds before the rename
            (self.base / "13.809.0.6322").mkdir()
            os.rename(self.active, self.base / "13.809.0.6322/EA Desktop")
            start = time.monotonic()
            while time.monotonic() - start < 1:
                if (self.active / "EABackgroundService.exe").exists():
                    found["ms"] = (time.monotonic() - start) * 1000
                    return
                time.sleep(0.0005)

        watcher = stagedlinks.Watcher(self.prefix)
        watcher.start()
        t = threading.Thread(target=installer)
        t.start()
        t.join()
        watcher.stop()
        self.assertIn("ms", found, "the link did not get into place")
        self.assertLess(found["ms"], 100)
        print(f"\n  the link was in place within {found['ms']:.1f} ms", file=sys.stderr)


class FromLogLineTest(unittest.TestCase):
    """In general: filling in the skipped link requests reported in Wine 10's log."""

    # a real line from installing the EA app (2026-10-20)
    EA_LINE = (r'0394:fixme:file:CreateSymbolicLinkW (L"C:\\Program Files\\Electronic Arts\\EA Desktop\\EA Desktop" '
               r'L"13.809.0.6322\\EA Desktop" 1): stub')

    def setUp(self):
        self.prefix = Path(tempfile.mkdtemp())
        self.drive_c = self.prefix / "drive_c"
        (self.drive_c / "Program Files/Electronic Arts/EA Desktop/13.809.0.6322/EA Desktop").mkdir(parents=True)
        dos = self.prefix / "dosdevices"
        dos.mkdir()
        (dos / "c:").symlink_to("../drive_c")
        (dos / "z:").symlink_to("/")

    def tearDown(self):
        shutil.rmtree(self.prefix)

    def test_real_ea_line(self):
        self.assertTrue(stagedlinks.from_log_line(self.prefix, self.EA_LINE))
        link = self.drive_c / "Program Files/Electronic Arts/EA Desktop/EA Desktop"
        self.assertEqual(os.readlink(link), "13.809.0.6322/EA Desktop")
        self.assertTrue(link.is_dir())
        self.assertTrue(stagedlinks.from_log_line(self.prefix, self.EA_LINE))  # the second time: already fine

    def test_absolute_target_and_case(self):
        (self.drive_c / "Games/Data").mkdir(parents=True)
        line = r'fixme:file:CreateSymbolicLinkW (L"C:\\GAMES\\current" L"C:\\games\\data" 1): stub'
        self.assertTrue(stagedlinks.from_log_line(self.prefix, line))
        link = self.drive_c / "Games/current"
        self.assertEqual(os.readlink(link), str(self.drive_c / "Games/Data"))

    def test_outside_prefix_skipped(self):
        line = r'fixme:file:CreateSymbolicLinkW (L"Z:\\tmp\\sloth-test-link" L"C:\\x" 0): stub'
        self.assertFalse(stagedlinks.from_log_line(self.prefix, line))
        self.assertFalse(os.path.lexists("/tmp/sloth-test-link"))

    def test_existing_folder_untouched(self):
        link = self.drive_c / "Program Files/Electronic Arts/EA Desktop/EA Desktop"
        link.mkdir()
        self.assertFalse(stagedlinks.from_log_line(self.prefix, self.EA_LINE))
        self.assertFalse(link.is_symlink())

    def test_other_lines_ignored(self):
        self.assertFalse(stagedlinks.from_log_line(self.prefix, "fixme:file:ReplaceFileW stub"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
