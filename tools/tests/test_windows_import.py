#!/usr/bin/env python3
"""Moving over from Windows (sloth_common/windows_import.py) on a made-up Windows drive: which programs of the
Start menu are recognised, which Steam games are found (also on a second drive, from libraryfolders.vdf), and how
they are copied into Steam's library. No mounting, Steam or Qt needed."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import windows_import as wi  # noqa: E402


def touch(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def manifest(appid, name, installdir, flags="4"):
    return (f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"StateFlags"\t\t"{flags}"\n'
            f'\t"installdir"\t\t"{installdir}"\n\t"LauncherPath"\t\t"C:\\\\Program Files (x86)\\\\Steam\\\\steam.exe"\n}}\n')


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sloth-winimport-"))
        self.c = self.tmp / "c"           # the Windows drive
        self.d = self.tmp / "d"           # a second drive with a Steam library
        self.home = self.c / "Users" / "Anna"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Programs(Base):
    def test_start_menu_and_store_apps(self):
        sm = self.c / wi.START_MENU
        user_sm = self.home / wi.USER_START_MENU
        for p in (sm / "Microsoft Edge.lnk", sm / "Word.lnk", sm / "LibreOffice 24.8" / "LibreOffice Writer.lnk",
                  sm / "Steam" / "Steam.lnk", sm / "Operator Tools.lnk", sm / "Epic Games Launcher.lnk",
                  user_sm / "Discord Inc" / "Discord.lnk", user_sm / "Spotify.lnk", user_sm / "desktop.ini"):
            touch(p)
        (self.home / "AppData/Local/Packages/5319275A.WhatsAppDesktop_cv1g1gvanyjgm").mkdir(parents=True)
        found = {p["id"]: p["instead"] for p in wi.programs(self.c, self.home)}
        self.assertEqual(found, {
            "org.libreoffice.LibreOffice": "",       # as itself, though Word is there too
            "com.spotify.Client": "",
            "com.discordapp.Discord": "",
            "com.rtosta.zapzap": "WhatsApp",         # a Microsoft Store app
            "com.valvesoftware.Steam": "",
            "com.heroicgameslauncher.hgl": "Epic Games",
        })  # no Edge (on every Windows), no Opera from "Operator Tools"

    def test_counterpart_alone(self):
        touch(self.c / wi.START_MENU / "Excel.lnk")
        self.assertEqual(wi.programs(self.c, self.home), [{"id": "org.libreoffice.LibreOffice",
                                                           "instead": "Microsoft Office"}])

    def test_every_app_is_in_the_wizard(self):
        sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-welcome"))
        from sloth_welcome import catalog
        for _pattern, app_id, _instead in wi.PROGRAMS:
            self.assertIsNotNone(catalog.find_app(app_id), app_id)


class SteamGames(Base):
    def make(self):
        steam = self.c / "Program Files (x86)" / "Steam" / "steamapps"
        touch(steam / "libraryfolders.vdf", (
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"\n\t}\n'
            '\t"1"\n\t{\n\t\t"path"\t\t"D:\\\\Games\\\\MySteam"\n\t}\n}\n').encode())
        touch(steam / "appmanifest_10.acf", manifest("10", "Alpha", "Alpha").encode())
        touch(steam / "common" / "Alpha" / "alpha.exe", b"a" * 100)
        touch(steam / "common" / "Alpha" / "data" / "level1.pak", b"b" * 50)
        touch(steam / "appmanifest_228980.acf", manifest("228980", "Steamworks Common Redistributables",
                                                         "Steamworks Shared").encode())
        touch(steam / "common" / "Steamworks Shared" / "x.exe")
        touch(steam / "appmanifest_30.acf", manifest("30", "Half done", "HalfDone", flags="1026").encode())
        touch(steam / "common" / "HalfDone" / "x.exe")
        other = self.d / "Games" / "MySteam" / "steamapps"   # only libraryfolders.vdf knows this path
        touch(other / "appmanifest_20.acf", manifest("20", "Beta", "Beta").encode())
        touch(other / "common" / "Beta" / "beta.exe", b"c" * 70)

    def test_found_on_both_drives(self):
        self.make()
        games = wi.steam_games([self.c, self.d])
        self.assertEqual([(g["appid"], g["name"], g["size"]) for g in games], [("10", "Alpha", 150), ("20", "Beta", 70)])

    def test_copy_into_steam(self):
        self.make()
        games = wi.steam_games([self.c, self.d])
        root = self.tmp / "linux-steam"
        progress = []
        r = wi.copy_games(games, root, on_progress=lambda d, t, n: progress.append((d, t)))
        self.assertEqual((r["games"], r["skipped"], r["failed"], r["bytes"]), (2, 0, [], 220))
        apps = root / "steamapps"
        self.assertEqual((apps / "common/Alpha/data/level1.pak").read_bytes(), b"b" * 50)
        self.assertIn('"installdir"\t\t"Beta"', (apps / "appmanifest_20.acf").read_text())
        self.assertEqual(progress[-1], (220, 220))
        self.assertEqual(list(apps.rglob("*.sloth-part")), [])
        again = wi.copy_games(games, root)  # already there: nothing copied
        self.assertEqual((again["games"], again["skipped"], again["bytes"]), (0, 2, 0))

    def test_no_manifest_for_a_broken_or_interrupted_copy(self):
        self.make()
        games = wi.steam_games([self.c, self.d])
        root = self.tmp / "linux-steam"
        real = shutil.copyfile

        def failing(src, dst, *a, **k):
            if str(src).endswith("beta.exe"):
                raise OSError("read error")
            return real(src, dst, *a, **k)

        with mock.patch.object(wi.shutil, "copyfile", failing):
            r = wi.copy_games(games, root)
        self.assertEqual((r["games"], r["failed"]), (1, ["Beta"]))
        self.assertFalse((root / "steamapps/appmanifest_20.acf").exists())  # Steam does not see a broken game
        r = wi.copy_games(games, root)  # the next try finishes it
        self.assertEqual((r["games"], r["skipped"]), (1, 1))
        shutil.rmtree(root)
        r = wi.copy_games(games, root, cancelled=lambda: True)
        self.assertEqual(r["games"], 0)
        self.assertEqual(list((root / "steamapps").glob("*.acf")), [])

    def test_bad_installdir_is_ignored(self):
        steam = self.c / "SteamLibrary" / "steamapps"
        touch(steam / "appmanifest_40.acf", manifest("40", "Evil", "..").encode())
        self.assertEqual(wi.steam_games([self.c]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
