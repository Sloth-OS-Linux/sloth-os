#!/usr/bin/env python3
"""Az EA app verziócseréjének (link a verziós mappára) pótlása: sloth_exe.stagedlinks.

Linuxon fut, Qt és Wine nélkül:
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
# a csomag __init__-je nélkül töltjük be (az a Qt-s részeket is behúzná)
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
        self.assertFalse(stagedlinks.fix(self.prefix))  # másodszor nincs teendő

    def test_update_moves_link_to_newest(self):
        self.stage("13.809.0.6322")
        stagedlinks.fix(self.prefix)
        self.stage("13.900.1.7000-1770576199")
        self.stage("13.95.0.1")  # régebbi, csak a szövegben „nagyobb”
        stagedlinks.fix(self.prefix)
        self.assertEqual(os.readlink(self.active), "13.900.1.7000-1770576199/EA Desktop")

    def test_real_folder_untouched(self):
        self.stage("13.809.0.6322")
        self.active.mkdir()
        self.assertFalse(stagedlinks.fix(self.prefix))
        self.assertFalse(self.active.is_symlink())

    def test_watcher_is_fast_enough(self):
        """Mint a telepítő: a fájlok az aktív mappába, aztán átnevezés a verziós helyre; a szolgáltatás
        néhány ezredmásodperc múlva már keresi a fájlt."""
        found = {}

        def installer():
            time.sleep(0.2)
            self.active.mkdir(parents=True)
            (self.active / "EABackgroundService.exe").write_text("x")
            time.sleep(0.3)  # a valódi telepítőnél a másolás másodpercekig tart az átnevezés előtt
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
        self.assertIn("ms", found, "a link nem került a helyére")
        self.assertLess(found["ms"], 100)
        print(f"\n  a link {found['ms']:.1f} ms alatt a helyén volt", file=sys.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
