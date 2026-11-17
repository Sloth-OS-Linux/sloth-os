#!/usr/bin/env python3
"""TV mode's other games in Steam's list: the binary VDF (sloth_common.apps.steam), tv-shortcuts add / remove (the
user's own non-Steam games stay), game_library.tv_launch, and tv-launch's look for a game's programs."""
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
from sloth_common import game_library  # noqa: E402
from sloth_common.apps import steam  # noqa: E402


def load(name):
    path = REPO / "files/system/usr/libexec/sloth-os" / name
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class BinaryVdfTest(unittest.TestCase):
    def test_round_trip(self):
        data = {"shortcuts": {"0": {"appid": -123456, "AppName": "Ünnep", "Exe": '"/a b/c"', "IsHidden": 0,
                                    "tags": {"0": "favorite"}}}}
        raw = steam.binary_vdf_dump(data)
        self.assertTrue(raw.startswith(b"\x00shortcuts\x00\x000\x00"))
        self.assertTrue(raw.endswith(b"\x08\x08\x08"))           # tags, the entry, shortcuts... and the file
        self.assertEqual(steam.binary_vdf_load(raw), data)

    def test_appid(self):
        a = steam.shortcut_appid('"/x"', "Game")
        self.assertEqual(a, steam.shortcut_appid('"/x"', "Game"))
        self.assertLess(a, 0)                                     # top bit set: negative as a signed number
        self.assertNotEqual(a, steam.shortcut_appid('"/x"', "Other"))


class ShortcutsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.m = load("tv-shortcuts")
        self.config = self.root / "userdata/12345/config"
        self.config.mkdir(parents=True)
        (self.root / "userdata/0/config").mkdir(parents=True)     # not an account
        own = {"shortcuts": {"0": {"appid": steam.shortcut_appid('"/opt/mine"', "Mine"), "AppName": "Mine",
                                   "Exe": '"/opt/mine"', "LaunchOptions": ""}}}
        (self.config / "shortcuts.vdf").write_bytes(steam.binary_vdf_dump(own))
        cover = self.root / "cover.jpg"
        cover.write_bytes(b"jpg")
        icon = self.root / "icon.png"
        icon.write_bytes(b"png")
        self.games = [
            {"id": "flatpak:net.supertuxkart.SuperTuxKart", "name": "SuperTuxKart", "source": "flatpak",
             "cover": "", "icon": str(icon), "launch": ["flatpak", "run", "x"], "folder": ""},
            {"id": "epic:Fortnite", "name": "Fortnite", "source": "epic", "cover": str(cover), "icon": "",
             "launch": ["xdg-open", "heroic://launch?appName=Fortnite&runner=legendary"], "folder": "/g"},
            {"id": "win:abc", "name": "mine", "source": "windows", "cover": "", "icon": "", "launch": ["x"],
             "folder": ""},                                       # same name as the user's own: left out
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def entries(self):
        data = steam.binary_vdf_load((self.config / "shortcuts.vdf").read_bytes())
        return list(data["shortcuts"].values())

    def test_add_and_remove(self):
        self.assertEqual(self.m.add(self.games, self.root), 2)
        names = [e["AppName"] for e in self.entries()]
        self.assertEqual(names, ["Mine", "Fortnite", "SuperTuxKart"])
        kart = self.entries()[2]
        self.assertEqual(kart["Exe"], self.m.EXE)
        self.assertEqual(kart["LaunchOptions"], "flatpak:net.supertuxkart.SuperTuxKart")
        u = kart["appid"] & 0xFFFFFFFF
        self.assertEqual(kart["icon"], str(self.config / f"grid/{u}_icon.png"))
        fort = self.entries()[1]["appid"] & 0xFFFFFFFF
        self.assertTrue((self.config / f"grid/{fort}p.jpg").is_file())
        self.assertFalse((self.root / "userdata/0/config/shortcuts.vdf").exists())
        # again (TV mode once more): no doubles
        self.m.add(self.games, self.root)
        self.assertEqual(len(self.entries()), 3)
        # TV mode ends: only the user's own stays, our pictures go
        self.m.remove(self.root)
        self.assertEqual([e["AppName"] for e in self.entries()], ["Mine"])
        self.assertFalse(list((self.config / "grid").glob("*")))
        self.assertTrue((self.config / "shortcuts.vdf.sloth-backup").is_file())

    def test_removed_game_goes(self):
        self.m.add(self.games, self.root)
        self.m.add(self.games[:1], self.root)                     # Fortnite was uninstalled
        self.assertEqual([e["AppName"] for e in self.entries()], ["Mine", "SuperTuxKart"])

    def test_no_file_yet(self):
        (self.config / "shortcuts.vdf").unlink()
        self.m.add(self.games[:1], self.root)
        self.assertEqual([e["AppName"] for e in self.entries()], ["SuperTuxKart"])


class LaunchTest(unittest.TestCase):
    def test_heroic_without_window(self):
        game = {"source": "gog", "launch": ["xdg-open", "heroic://launch?appName=1&runner=gog"]}
        cmd = game_library.tv_launch(game)
        self.assertEqual(cmd[-3:], ["--no-gui", "--no-sandbox", "heroic://launch?appName=1&runner=gog"])

    def test_others_as_they_are(self):
        game = {"source": "flatpak", "launch": ["flatpak", "run", "x"]}
        self.assertEqual(game_library.tv_launch(game), ["flatpak", "run", "x"])

    def test_runs_from_folder(self):
        m = load("tv-launch")
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(m.runs_from(folder))
            p = subprocess.Popen(["sleep", "30"], cwd=folder)
            try:
                time.sleep(0.2)
                self.assertTrue(m.runs_from(folder))
            finally:
                p.kill()
                p.wait()
            self.assertFalse(m.runs_from(folder))
            self.assertFalse(m.runs_from("/"))
        self.assertTrue(os.path.isdir("/proc"))


if __name__ == "__main__":
    unittest.main()
