#!/usr/bin/env python3
"""What's new after an update (sloth_center/whats_new.py): told once per version, never on a fresh install, and
every note is a Sloth Center text in English."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import whats_new as wn  # noqa: E402


class WhatsNew(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.osr = self.tmp / "os-release"
        self.version("1.5")
        self.patches = [mock.patch.object(wn, "OS_RELEASE", self.osr),
                        mock.patch.object(wn, "SEEN", self.tmp / "state/seen"),
                        mock.patch.object(wn, "WELCOME_DONE", self.tmp / "welcome-done"),
                        mock.patch.object(wn.quiet_hours, "defer", return_value=False)]
        for p in self.patches:
            p.start()
        self.run_mock = mock.patch.object(wn.subprocess, "run", return_value=mock.Mock(stdout=""))
        self.notify = self.run_mock.start()

    def tearDown(self):
        self.run_mock.stop()
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def version(self, v):
        self.osr.write_text(f'NAME="Sloth OS"\nVERSION="{v} (Fedora Atomic 44)"\nVERSION_ID=44\n')

    def test_version(self):
        self.assertEqual(wn.current_version(), "1.5")

    def test_fresh_install_is_quiet(self):
        wn.main()                                   # Welcome still ahead
        self.notify.assert_not_called()
        self.assertEqual((self.tmp / "state/seen").read_text().strip(), "1.5")

    def test_update_from_before(self):
        (self.tmp / "welcome-done").touch()         # an account from 1.4.2, which had no "seen" yet
        wn.main()
        self.assertEqual(self.notify.call_count, 1)
        args = self.notify.call_args[0][0]
        self.assertIn("Sloth OS 1.5 is here", args)
        wn.main()                                   # only once
        self.assertEqual(self.notify.call_count, 1)

    def test_version_without_notes(self):
        (self.tmp / "welcome-done").touch()
        self.version("9.9")
        wn.main()
        self.notify.assert_not_called()

    def test_notes_are_english_texts(self):
        for version, notes in wn.NOTES.items():
            self.assertTrue(notes, version)
            self.assertEqual(wn.notes(version), notes)   # untranslated: the English text itself


if __name__ == "__main__":
    unittest.main(verbosity=2)
