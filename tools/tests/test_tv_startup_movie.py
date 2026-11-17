#!/usr/bin/env python3
"""TV mode's start-up video (files/system/usr/libexec/sloth-os/tv-startup-movie): the video goes into Steam's folder
and is picked in config.vdf only while Steam is at Default."""
import hashlib
import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "files/system/usr/libexec/sloth-os/tv-startup-movie"
VIDEO = REPO / "files/system/usr/share/sloth-os/tv/startup.webm"


def load():
    loader = importlib.machinery.SourceFileLoader("tv_startup_movie", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


DEFAULT = '''"InstallConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"CompatToolMapping"
\t\t\t\t{
\t\t\t\t}
\t\t\t\t"StartupMovie"
\t\t\t\t{
\t\t\t\t\t"MovieID"\t\t"0"
\t\t\t\t\t"LocalPath"\t\t""
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\t"Customization"
\t{
\t\t"StartupMovie"
\t\t{
\t\t\t"MovieID"\t\t"0"
\t\t\t"LocalPath"\t\t""
\t\t\t"Shuffle"\t\t"0"
\t\t}
\t}
}
'''


class StartupMovieTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.m = load()
        steam = home / "steam"
        self.m.INTRO = VIDEO
        self.m.CONFIG = steam / "config/config.vdf"
        self.m.MOVIES = steam / "config/uioverrides/movies"
        self.m.STATE = home / "state"
        self.m.PICKED = self.m.STATE / "tv-startup-movie.done"
        self.vdf = self.m._vdf()
        self.vdf.steam_running = lambda: False
        self.m._vdf = lambda: self.vdf
        self.m.CONFIG.parent.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def movies(self):
        items = self.vdf.parse(self.m.CONFIG.read_text())
        return [(self.m.value(b, "MovieID"), self.m.value(b, "LocalPath")) for b in self.m.movie_blocks(items, self.vdf)[1]]

    def test_default_becomes_ours_once(self):
        self.m.CONFIG.write_text(DEFAULT)
        self.m.main()
        self.assertEqual(self.movies(), [("0", self.m.LOCAL_PATH)] * 2)
        self.assertEqual((self.m.MOVIES / self.m.NAME).read_bytes(), VIDEO.read_bytes())
        self.assertIn('"Shuffle"\t\t"0"', self.m.CONFIG.read_text())        # the rest is kept
        self.assertIn('"CompatToolMapping"', self.m.CONFIG.read_text())
        # the user goes back to Default: it stays
        self.m.CONFIG.write_text(DEFAULT)
        self.m.main()
        self.assertEqual(self.movies(), [("0", "")] * 2)

    def test_users_own_pick_stays(self):
        own = DEFAULT.replace('"LocalPath"\t\t""\n\t\t\t"Shuffle"', '"LocalPath"\t\t"/appcache/startupmovies/x.webm"\n\t\t\t"Shuffle"')
        own = own.replace('"MovieID"\t\t"0"\n\t\t\t"LocalPath"\t\t"/app', '"MovieID"\t\t"123"\n\t\t\t"LocalPath"\t\t"/app')
        self.m.CONFIG.write_text(own)
        self.m.main()
        self.assertEqual(self.m.CONFIG.read_text(), own)
        self.assertTrue(self.m.PICKED.exists())

    def test_no_block_yet(self):
        self.m.CONFIG.write_text('"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t}\n}\n')
        self.m.main()
        self.assertEqual(self.movies(), [("0", self.m.LOCAL_PATH)])

    def test_waits_for_steam(self):
        self.m.main()                                   # no config.vdf yet: nothing made
        self.assertFalse(self.m.CONFIG.exists())
        self.assertFalse(self.m.PICKED.exists())
        self.m.CONFIG.write_text(DEFAULT)
        self.vdf.steam_running = lambda: True
        self.m.main()
        self.assertEqual(self.m.CONFIG.read_text(), DEFAULT)
        self.assertFalse(self.m.PICKED.exists())
        self.vdf.steam_running = lambda: False
        self.m.main()
        self.assertEqual(self.movies(), [("0", self.m.LOCAL_PATH)] * 2)

    def picked_by_hand(self, name):
        return DEFAULT.replace('"LocalPath"\t\t""\n\t\t\t"Shuffle"',
                               f'"LocalPath"\t\t"/uioverrides/movies/{name}"\n\t\t\t"Shuffle"')

    def test_pick_of_a_gone_video_becomes_ours(self):
        """The HP, 2026-11-17: our old deck_startup.webm was picked by hand, the update removed it (Steam then played
        Valve's video), and the first run took the pick for the user's own. Also with the "done" mark there."""
        self.m.STATE.mkdir(parents=True)
        self.m.PICKED.touch()
        self.m.CONFIG.write_text(self.picked_by_hand("deck_startup.webm"))
        self.m.main()
        self.assertEqual(self.movies()[0], ("0", self.m.LOCAL_PATH))

    def test_pick_of_an_existing_video_stays(self):
        self.m.MOVIES.mkdir(parents=True)
        (self.m.MOVIES / "mine.webm").write_bytes(b"the user's own")
        own = self.picked_by_hand("mine.webm")
        self.m.CONFIG.write_text(own)
        self.m.main()
        self.assertEqual(self.m.CONFIG.read_text(), own)
        self.m.main()                                   # later runs too
        self.assertEqual(self.m.CONFIG.read_text(), own)

    def test_old_copy_removed_only_if_ours(self):
        self.m.MOVIES.mkdir(parents=True)
        old = self.m.MOVIES / "deck_startup.webm"
        old.write_bytes(b"older ours")
        (self.m.MOVIES / ".sloth-os-startup").write_text(hashlib.sha256(b"older ours").hexdigest() + "\n")
        self.m.main()
        self.assertFalse(old.exists())
        old.write_bytes(b"put there by hand")
        self.m.main()
        self.assertTrue(old.exists())


if __name__ == "__main__":
    unittest.main()
