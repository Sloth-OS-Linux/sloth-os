#!/usr/bin/env python3
"""Moving over from Windows (sloth_common/windows_import.py) on a made-up Windows drive: which programs of the
Start menu are recognised, which Steam games are found (also on a second drive, from libraryfolders.vdf), and how
they are copied into Steam's library. No mounting, Steam or Qt needed."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import browser_bookmarks as bb  # noqa: E402
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


MANIFEST = '''Some Game:
  files:
    "<base>/save":
      tags:
        - save
  steam:
    id: 999
Hollow Knight:
  cloud:
    gog: true
  files:
    "<base>/hollow_knight_Data/Config.ini":
      tags:
        - config
    "<home>/AppData/LocalLow/Team Cherry/Hollow Knight/*.dat":
      tags:
        - save
      when:
        - os: windows
    "<home>/Library/Application Support/unity.Team Cherry.Hollow Knight":
      tags:
        - save
      when:
        - os: mac
  id:
    lutris: hollow-knight
  steam:
    id: 10
Clouded:
  cloud:
    steam: true
  files:
    "<winAppData>/Clouded":
      tags:
        - save
  steam:
    id: 20
'''


class Saves(Base):
    GAMES = [{"appid": "10", "name": "Alpha"}, {"appid": "20", "name": "Beta"}]

    def test_manifest(self):
        found = wi.save_locations(MANIFEST, ["10", "20", "30"])
        self.assertEqual(found["10"], (False, ["<home>/AppData/LocalLow/Team Cherry/Hollow Knight/*.dat"]))
        self.assertEqual(found["20"], (True, ["<winAppData>/Clouded"]))
        self.assertNotIn("30", found)

    def test_into_the_proton_environment(self):
        low = self.home / "AppData" / "LocalLow" / "team cherry" / "Hollow Knight"   # another case on NTFS
        touch(low / "user1.dat", b"save1")
        touch(low / "user2.dat", b"save2")
        touch(low / "screenshot.png")
        touch(self.home / "AppData/Roaming/Clouded/cloud.sav")
        root = self.tmp / "linux-steam"
        user = root / "steamapps/compatdata/10/pfx/drive_c/users/steamuser"
        touch(user / "AppData/LocalLow/team cherry/Hollow Knight/user2.dat", b"newer, played here")
        done = wi.copy_saves(self.home, self.GAMES, root, manifest_text=MANIFEST)
        self.assertEqual(done, ["Alpha"])
        self.assertEqual((user / "AppData/LocalLow/team cherry/Hollow Knight/user1.dat").read_bytes(), b"save1")
        self.assertEqual((user / "AppData/LocalLow/team cherry/Hollow Knight/user2.dat").read_bytes(),
                         b"newer, played here")  # never overwritten
        self.assertFalse((user / "AppData/LocalLow/team cherry/Hollow Knight/screenshot.png").exists())
        self.assertFalse((root / "steamapps/compatdata/20").exists())  # Steam Cloud brings that one

    def test_documents_in_onedrive(self):
        manifest = 'Docs Game:\n  files:\n    "<winDocuments>/My Games/Docs Game":\n      tags:\n        - save\n' \
                   '  steam:\n    id: 10\n'
        touch(self.home / "OneDrive" / "Documents" / "My Games" / "Docs Game" / "slot1.sav", b"s")
        root = self.tmp / "linux-steam"
        self.assertEqual(wi.copy_saves(self.home, self.GAMES[:1], root, manifest_text=manifest), ["Alpha"])
        self.assertTrue((root / "steamapps/compatdata/10/pfx/drive_c/users/steamuser/Documents/My Games/Docs Game/slot1.sav")
                        .is_file())

    def test_offline(self):
        with mock.patch.object(wi, "_fetch", side_effect=OSError("offline")), \
                mock.patch.object(wi, "CACHE", self.tmp / "none.yaml"):
            self.assertEqual(wi.copy_saves(self.home, self.GAMES, self.tmp / "s"), [])


class Proton(Base):
    def test_store_answer(self):
        with mock.patch.object(wi, "_fetch", return_value=b'{"620": {"success": true, "data": {"platforms": '
                                                          b'{"windows": true, "mac": true, "linux": true}}}}'):
            self.assertTrue(wi.has_linux_version("620"))
        with mock.patch.object(wi, "_fetch", side_effect=OSError("offline")):
            self.assertIsNone(wi.has_linux_version("620"))

    def test_force_proton(self):
        root = self.tmp / "steam"
        self.assertEqual(wi.force_proton(root, ["620"]), 1)  # no config.vdf yet (Steam never started)
        mapping = self.mapping(root)
        self.assertEqual(mapping["620"]["name"], "proton_experimental")
        mapping["0"] = {"name": "proton_9", "config": "", "priority": "75"}
        mapping["620"]["name"] = "proton_8"  # the user's own choice
        cfg = root / "config/config.vdf"
        cfg.write_text(wi.steam.vdf_dump({"InstallConfigStore": {"Software": {"Valve": {"Steam": {
            "CompatToolMapping": mapping, "AutoUpdateWindowEnabled": "0"}}}}}))
        self.assertEqual(wi.force_proton(root, ["620", "730"]), 1)
        mapping = self.mapping(root)
        self.assertEqual((mapping["620"]["name"], mapping["730"]["name"]), ("proton_8", "proton_9"))
        self.assertIn("AutoUpdateWindowEnabled", cfg.read_text())  # the rest of the file stays

    @staticmethod
    def mapping(root):
        data = wi.steam.vdf_load((root / "config/config.vdf").read_text())
        return data["InstallConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]


class SavedGames(Base):
    def test_saved_games_folder(self):
        manifest = 'SG:\n  files:\n    "<home>/Saved Games/SG Studio/Profile":\n      tags:\n        - save\n' \
                   '  steam:\n    id: 10\n'
        touch(self.home / "Saved Games" / "SG Studio" / "Profile" / "slot.sav", b"s")
        root = self.tmp / "linux-steam"
        self.assertEqual(wi.copy_saves(self.home, [{"appid": "10", "name": "SG"}], root, manifest_text=manifest),
                         ["SG"])
        self.assertTrue((root / "steamapps/compatdata/10/pfx/drive_c/users/steamuser/Saved Games/SG Studio/Profile"
                         / "slot.sav").is_file())


class Libraries(Base):
    def test_second_library_and_finish(self):
        own, second = self.tmp / "steam", self.tmp / "disk2" / "SteamLibrary"
        (own / "steamapps").mkdir(parents=True)
        (second / "steamapps").mkdir(parents=True)
        (own / "steamapps/libraryfolders.vdf").write_text(wi.steam.vdf_dump({"libraryfolders": {
            "0": {"path": str(own)}, "1": {"path": str(second)}, "2": {"path": str(self.tmp / "gone")}}}))
        with mock.patch.object(wi, "steam_target", return_value=own):
            libs = wi.steam_libraries()
        self.assertEqual([lib["path"] for lib in libs], [str(own), str(second)])   # a missing one is left out
        touch(second / "steamapps/appmanifest_10.acf")
        touch(self.home / "AppData/LocalLow/Team Cherry/Hollow Knight/user1.dat")
        with mock.patch.object(wi, "_saves_manifest", return_value=MANIFEST), \
                mock.patch.object(wi, "has_linux_version", return_value=False):
            out = wi.finish_games([{"appid": "10", "name": "Alpha"}], self.home, root=own, library=second)
        self.assertEqual(out["saves"], ["Alpha"])
        self.assertTrue((second / "steamapps/compatdata/10/pfx/drive_c/users/steamuser/AppData/LocalLow"
                         "/Team Cherry/Hollow Knight/user1.dat").is_file())   # next to the game, not in Steam's own


TREE = [{"title": "Google Chrome", "children": [
    {"title": "Sloth OS", "url": "https://sloth-os-linux.github.io/"},
    {"title": "Sub", "children": [{"title": "Mag", "url": "https://fedoramagazine.org/"}]}]}]

FIREFOX_SCHEMA = """
    CREATE TABLE moz_origins (id INTEGER PRIMARY KEY, prefix TEXT NOT NULL, host TEXT NOT NULL,
      frecency INTEGER NOT NULL, recalc_frecency INTEGER NOT NULL DEFAULT 0,
      recalc_alt_frecency INTEGER NOT NULL DEFAULT 0, UNIQUE (host, prefix));
    CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url LONGVARCHAR, title LONGVARCHAR, rev_host LONGVARCHAR,
      visit_count INTEGER DEFAULT 0, hidden INTEGER DEFAULT 0 NOT NULL, typed INTEGER DEFAULT 0 NOT NULL,
      frecency INTEGER DEFAULT -1 NOT NULL, last_visit_date INTEGER, guid TEXT,
      foreign_count INTEGER DEFAULT 0 NOT NULL, url_hash INTEGER DEFAULT 0 NOT NULL, origin_id INTEGER,
      recalc_frecency INTEGER NOT NULL DEFAULT 0, recalc_alt_frecency INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INTEGER, fk INTEGER DEFAULT NULL, parent INTEGER,
      position INTEGER, title LONGVARCHAR, keyword_id INTEGER, folder_type TEXT, dateAdded INTEGER,
      lastModified INTEGER, guid TEXT, syncStatus INTEGER NOT NULL DEFAULT 0,
      syncChangeCounter INTEGER NOT NULL DEFAULT 1);
    INSERT INTO moz_bookmarks (id, type, parent, position, title, guid) VALUES
      (1, 2, 0, 0, '', 'root________'), (3, 2, 1, 1, 'toolbar', 'toolbar_____');
    INSERT INTO moz_origins (id, prefix, host, frecency) VALUES (1, 'https://', 'fedoramagazine.org', 100);
    INSERT INTO moz_places (id, url, rev_host, frecency, foreign_count, url_hash, origin_id) VALUES
      (1, 'https://fedoramagazine.org/', 'gro.enizagamarodef.', 100, 1, 47360361921933, 1);
    INSERT INTO moz_bookmarks (type, fk, parent, position, title, guid) VALUES (1, 1, 3, 0, 'Mag', 'aaaaaaaaaaaa');
"""


class Bookmarks(Base):
    """Real Firefox 159 and Chromium 156 were checked by hand: they show the bookmarks written this way, and
    Firefox's own database check (PlacesDBUtils.checkAndFixDatabase) finds it coherent."""

    def setUp(self):
        super().setUp()
        self.apps, self.flatpaks = self.tmp / "var-app", self.tmp / "flatpak"
        self.patches = [mock.patch.object(bb, "APPS", self.apps),
                        mock.patch.object(bb, "FLATPAK_DIRS", (self.flatpaks,)),
                        mock.patch.object(bb, "PENDING", self.tmp / "pending.json"),
                        mock.patch.object(bb, "_running", return_value=set())]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def install(self, app_id):
        (self.flatpaks / app_id).mkdir(parents=True)

    def test_windows_sources(self):
        touch(self.home / "AppData/Roaming/Opera Software/Opera Stable/Bookmarks", json.dumps(
            {"roots": {"bookmark_bar": {"type": "folder", "name": "Bar", "children": [
                {"type": "url", "name": "O", "url": "https://opera.example/"}]}}}).encode())
        folders = wi.bookmark_folders(self.home)
        self.assertEqual(folders[0]["title"], "Opera")
        self.assertEqual(wi.count_bookmarks(folders), 1)

    def test_url_hash(self):   # values from a profile made by Firefox 159
        self.assertEqual(bb.url_hash("https://fedoramagazine.org/"), 47360361921933)
        self.assertEqual(bb.url_hash("http://fedoraplanet.org/"), 125509191667383)
        self.assertEqual(bb.url_hash("place:sort=8&maxResults=10"), 268505095842199)

    def test_chromium_existing_profile(self):
        self.install("com.brave.Browser")
        data = self.apps / "com.brave.Browser/config/BraveSoftware/Brave-Browser"
        touch(data / "Local State", json.dumps({"profile": {"last_used": "Profile 1"}}).encode())
        mine = {"id": "7", "type": "url", "name": "Mine", "url": "https://mine.example/"}
        touch(data / "Profile 1/Bookmarks", json.dumps({"checksum": "abc", "version": 1, "roots": {
            "bookmark_bar": {"id": "1", "type": "folder", "name": "Bar", "children": [mine]},
            "other": {"id": "2", "type": "folder", "name": "Other", "children": []},
            "synced": {"id": "3", "type": "folder", "name": "Mobile", "children": []}}}).encode())
        bb.save_pending(TREE, "From Windows")
        self.assertEqual(bb.apply_pending(), ["com.brave.Browser"])
        out = json.loads((data / "Profile 1/Bookmarks").read_text(encoding="utf-8"))
        self.assertNotIn("checksum", out)
        bar = out["roots"]["bookmark_bar"]["children"]
        self.assertEqual(bar[0], mine)                     # what was there stays
        self.assertEqual(bar[1]["name"], "From Windows")
        ids = []

        def walk(n):
            ids.append(n["id"])
            for c in n.get("children", []):
                walk(c)
        for r in out["roots"].values():
            walk(r)
        self.assertEqual(len(ids), len(set(ids)))          # no id twice
        self.assertEqual(bb.apply_pending(), [])           # only once
        bb.save_pending(TREE, "From Windows")              # brought over again: the same bookmarks
        self.assertEqual(bb.apply_pending(), [])
        bb.save_pending(TREE + [{"title": "Edge", "children": [{"title": "N", "url": "https://n.example/"}]}],
                        "From Windows")                    # new ones on Windows meanwhile
        self.assertEqual(bb.apply_pending(), ["com.brave.Browser"])

    def test_chromium_never_started_and_running(self):
        self.install("com.google.Chrome")
        self.install("org.chromium.Chromium")
        bb.save_pending(TREE, "From Windows")
        with mock.patch.object(bb, "_running", return_value={"org.chromium.Chromium"}):
            self.assertEqual(bb.apply_pending(), ["com.google.Chrome"])
        made = json.loads((self.apps / "com.google.Chrome/config/google-chrome/Default/Bookmarks")
                          .read_text(encoding="utf-8"))
        self.assertEqual(made["roots"]["bookmark_bar"]["children"][0]["children"][0]["name"], "Google Chrome")
        self.assertEqual(bb.apply_pending(), ["org.chromium.Chromium"])   # once it is closed

    def test_firefox(self):
        self.install("org.mozilla.firefox")
        bb.save_pending(TREE, "From Windows")
        self.assertEqual(bb.apply_pending(), [])           # no profile before its first start
        root = self.apps / "org.mozilla.firefox/config/mozilla/firefox"
        touch(root / "profiles.ini", b"[Profile0]\nName=default-release\nIsRelative=1\nPath=ab.default-release\n\n"
                                     b"[Install4F96D1932A9F858E]\nDefault=ab.default-release\nLocked=1\n")
        root.joinpath("ab.default-release").mkdir()
        con = sqlite3.connect(root / "ab.default-release/places.sqlite")
        con.executescript(FIREFOX_SCHEMA)
        con.commit()
        con.close()
        self.assertEqual(bb.apply_pending(), ["org.mozilla.firefox"])
        con = sqlite3.connect(root / "ab.default-release/places.sqlite")
        rows = con.execute("SELECT b.title, b.position, p.url, p.foreign_count, p.url_hash, o.host "
                           "FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk "
                           "LEFT JOIN moz_origins o ON o.id = p.origin_id WHERE b.id > 4 ORDER BY b.id").fetchall()
        con.close()
        self.assertEqual(rows[0][:2], ("From Windows", 1))  # after what was on the toolbar
        self.assertIn(("Sloth OS", 0, "https://sloth-os-linux.github.io/", 1,
                       bb.url_hash("https://sloth-os-linux.github.io/"), "sloth-os-linux.github.io"), rows)
        self.assertIn(("Mag", 0, "https://fedoramagazine.org/", 2, 47360361921933, "fedoramagazine.org"), rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)
