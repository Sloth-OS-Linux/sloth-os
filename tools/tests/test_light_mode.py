#!/usr/bin/env python3
"""Lighter mode for weak computers (sloth_common/light_mode.py, sloth_center/light_mode_auto.py).

The weak-computer check runs anywhere; turning it on and off needs KDE's own kwriteconfig6 and balooctl6 (run it in
the image: they write the real files, which are then read back)."""
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

from sloth_common import light_mode as lm  # noqa: E402

KDE_TOOLS = bool(shutil.which("kwriteconfig6") and shutil.which("balooctl6"))


class ReasonsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dri = self.tmp / "dri"
        self.dri.mkdir()
        (self.dri / "card0").touch()
        (self.dri / "renderD128").touch()

    def meminfo(self, kb):
        p = self.tmp / "meminfo"
        p.write_text(f"MemTotal:       {kb} kB\nMemFree:        1000 kB\n")
        return p

    def test_a_good_computer_is_not_weak(self):
        self.assertEqual(lm.reasons(self.meminfo(16_000_000), self.dri, threads=8), [])

    def test_4_gb_counts_as_little_memory_but_6_gb_does_not(self):
        self.assertEqual(lm.reasons(self.meminfo(3_800_000), self.dri, threads=4), ["memory"])
        self.assertEqual(lm.reasons(self.meminfo(5_700_000), self.dri, threads=4), [])

    def test_two_threads_and_no_render_node(self):
        (self.dri / "renderD128").unlink()
        self.assertEqual(lm.reasons(self.meminfo(8_000_000), self.dri, threads=2), ["processor", "graphics"])
        self.assertEqual(lm.reasons(self.meminfo(8_000_000), self.tmp / "missing", threads=4), ["graphics"])

    def test_unreadable_meminfo_is_not_a_reason(self):
        self.assertEqual(lm.reasons(self.tmp / "nope", self.dri, threads=4), [])


@unittest.skipUnless(KDE_TOOLS, "needs kwriteconfig6 and balooctl6 (run it in the image)")
class OnOffTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.cfg = self.home / ".config"
        self.cfg.mkdir()
        self.env = mock.patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.cfg)})
        self.env.start()
        self.paths = mock.patch.multiple(lm, CONFIG_HOME=self.cfg, STATE=self.cfg / "sloth-os/light-mode.json")
        self.paths.start()

    def tearDown(self):
        self.paths.stop()
        self.env.stop()

    def read(self, file, group, key):
        return lm._read(file, group, key)

    def test_on_then_off_puts_everything_back(self):
        # someone had slower animations set by hand, blur not mentioned at all
        (self.cfg / "kdeglobals").write_text("[KDE]\nAnimationDurationFactor=2\nSingleClick=false\n")
        self.assertTrue(lm.set_on(True))
        self.assertTrue(lm.is_on())
        self.assertEqual(self.read("kdeglobals", "KDE", "AnimationDurationFactor"), "0")
        self.assertEqual(self.read("kwinrc", "Plugins", "blurEnabled"), "false")
        self.assertEqual(self.read("baloofilerc", "General", "only basic indexing"), "true")
        self.assertTrue(lm.set_on(False))
        self.assertFalse(lm.is_on())
        self.assertEqual(self.read("kdeglobals", "KDE", "AnimationDurationFactor"), "2")
        self.assertEqual(self.read("kdeglobals", "KDE", "SingleClick"), "false")        # the rest untouched
        self.assertIsNone(self.read("kwinrc", "Plugins", "blurEnabled"))               # not there before
        self.assertNotEqual(self.read("baloofilerc", "General", "only basic indexing"), "true")
        self.assertEqual(lm.load_state()["decided"], "user")

    def test_twice_on_keeps_the_first_before_values(self):
        lm.set_on(True)
        lm.set_on(True)        # must not save the lighter values as "before"
        lm.set_on(False)
        self.assertIsNone(self.read("kdeglobals", "KDE", "AnimationDurationFactor"))

    def test_auto_runs_once_and_never_overrides_the_users_choice(self):
        from sloth_center import light_mode_auto as auto
        with mock.patch.object(auto.light_mode, "reasons", return_value=["memory"]), \
                mock.patch.object(auto, "notify", return_value="") as notify:
            auto.main()
            self.assertTrue(lm.is_on())
            self.assertEqual(lm.load_state()["decided"], "auto")
            self.assertIn("little memory", notify.call_args[0][1])
            lm.set_on(False)               # the user turns it off in Sloth Center
            auto.main()                    # the next sign-in
            self.assertFalse(lm.is_on())
            self.assertEqual(notify.call_count, 1)

    def test_auto_does_nothing_on_a_good_computer(self):
        from sloth_center import light_mode_auto as auto
        with mock.patch.object(auto.light_mode, "reasons", return_value=[]), \
                mock.patch.object(auto, "notify") as notify:
            auto.main()
        self.assertFalse(lm.is_on())
        self.assertEqual(lm.load_state(), {})
        notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
