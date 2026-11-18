#!/usr/bin/env python3
"""Moving over from another Linux on the same computer (sloth_common/windows_import.py, its Linux part) on made-up
drives laid out as the common systems lay them out: Ubuntu's ext4, Fedora's btrfs (root/home subvolumes), Ubuntu's
btrfs (@/@home), a separate /home partition, Fedora Atomic's ostree. Which partitions count (lsblk's answer made up),
the accounts and their localised folders, the bookmarks, the apps, the Steam games with their Proton environments,
and the copying. No mounting, Steam or Qt needed."""
import json
import shutil
import sqlite3
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
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def manifest(appid, name, installdir):
    return (f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{name}"\n\t"StateFlags"\t\t"4"\n'
            f'\t"installdir"\t\t"{installdir}"\n}}\n')


def firefox_places(path, url, title):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);
        CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, parent INTEGER, type INTEGER, title TEXT, fk INTEGER,
                                    position INTEGER);
        INSERT INTO moz_bookmarks VALUES (1, 0, 2, '', NULL, 0);
        INSERT INTO moz_bookmarks VALUES (2, 1, 2, 'toolbar', NULL, 0);
    """)
    con.execute("INSERT INTO moz_places VALUES (1, ?)", (url,))
    con.execute("INSERT INTO moz_bookmarks VALUES (3, 2, 1, ?, 1, 0)", (title,))
    con.commit()
    con.close()


USER_DIRS_HU = '''# This file is written by xdg-user-dirs-update
XDG_DESKTOP_DIR="$HOME/Asztal"
XDG_DOWNLOAD_DIR="$HOME/Letöltések"
XDG_DOCUMENTS_DIR="$HOME/Dokumentumok"
XDG_MUSIC_DIR="$HOME/Zene"
XDG_PICTURES_DIR="$HOME/Képek"
XDG_VIDEOS_DIR="$HOME/Videók"
XDG_TEMPLATES_DIR="$HOME/Sablonok"
XDG_PUBLICSHARE_DIR="/srv/public"
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sloth-linuximport-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Layouts(Base):
    def ubuntu_ext4(self):
        mnt = self.tmp / "ubuntu"
        (mnt / "etc").mkdir(parents=True)
        touch(mnt / "usr/share/applications/firefox.desktop", "[Desktop Entry]\nName=Firefox Web Browser\n")
        touch(mnt / "usr/share/applications/org.gimp.GIMP.desktop", "[Desktop Entry]\nName=GNU Image Manipulation Program\n")
        touch(mnt / "var/lib/snapd/desktop/applications/spotify_spotify.desktop", "[Desktop Entry]\nName=Spotify\n")
        home = mnt / "home" / "anna"
        touch(home / ".bashrc")
        touch(home / ".config/user-dirs.dirs", USER_DIRS_HU)
        touch(home / "Dokumentumok/levél.odt", b"12345")
        touch(home / "Képek/nyár/tenger.jpg", b"1234567")
        touch(home / "Asztal/régi.desktop", b"[Desktop Entry]")
        touch(home / ".local/share/flatpak/app/org.videolan.VLC/current", b"")
        touch(home / ".local/share/flatpak/app/org.kde.kdenlive/current", b"")
        (mnt / "home" / "lost+found").mkdir()
        return mnt, home

    def test_ubuntu_ext4_user_and_localised_folders(self):
        mnt, home = self.ubuntu_ext4()
        users = wi.users(mnt)
        self.assertEqual([u["name"] for u in users], ["anna"])
        u = users[0]
        self.assertEqual(u["kind"], "linux")
        self.assertEqual(u["folders"]["documents"], 5)
        self.assertEqual(u["folders"]["pictures"], 7)
        self.assertEqual(Path(u["dirs"]["documents"]), home / "Dokumentumok")
        self.assertEqual(Path(u["dirs"]["downloads"]), home / "Letöltések")

    def test_ubuntu_ext4_apps(self):
        mnt, home = self.ubuntu_ext4()
        ids = [p["id"] for p in wi.users(mnt)[0]["programs"]]
        for app in ("org.mozilla.firefox", "org.gimp.GIMP", "com.spotify.Client", "org.videolan.VLC",
                    "org.kde.kdenlive"):
            self.assertIn(app, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_fedora_btrfs_root_and_home_subvolumes(self):
        mnt = self.tmp / "fedora"
        (mnt / "root" / "etc").mkdir(parents=True)
        touch(mnt / "root/var/lib/flatpak/app/org.mozilla.Thunderbird/current", b"")
        touch(mnt / "home/bob/.config/x")
        touch(mnt / "home/bob/Documents/a.txt", b"abc")
        users = wi.users(mnt)
        self.assertEqual([u["name"] for u in users], ["bob"])
        self.assertIn("org.mozilla.Thunderbird", [p["id"] for p in users[0]["programs"]])

    def test_ubuntu_btrfs_at_subvolumes(self):
        mnt = self.tmp / "ubtrfs"
        (mnt / "@" / "etc").mkdir(parents=True)
        touch(mnt / "@home/dora/.profile")
        touch(mnt / "@home/dora/Music/song.mp3", b"mp3")
        self.assertEqual([u["name"] for u in wi.users(mnt)], ["dora"])

    def test_separate_home_partition(self):
        mnt = self.tmp / "homepart"
        touch(mnt / "carl/.bashrc")
        touch(mnt / "carl/Pictures/p.png", b"png")
        (mnt / "lost+found").mkdir()
        self.assertEqual([u["name"] for u in wi.users(mnt)], ["carl"])

    def test_fedora_atomic_ostree(self):
        mnt = self.tmp / "atomic"
        touch(mnt / "ostree/deploy/fedora/var/lib/flatpak/app/com.discordapp.Discord/current", b"")
        touch(mnt / "ostree/deploy/fedora/var/home/eve/.bashrc")
        touch(mnt / "ostree/deploy/fedora/var/home/eve/Videos/v.mkv", b"mkv")
        users = wi.users(mnt)
        self.assertEqual([u["name"] for u in users], ["eve"])
        self.assertIn("com.discordapp.Discord", [p["id"] for p in users[0]["programs"]])

    def test_not_a_system(self):
        mnt = self.tmp / "data"
        touch(mnt / "Movies/film.mkv", b"x")
        self.assertEqual(wi.users(mnt), [])

    def test_user_dirs_outside_home_ignored(self):
        home = self.tmp / "h"
        touch(home / ".config/user-dirs.dirs", 'XDG_DOCUMENTS_DIR="/mnt/data/docs"\nXDG_MUSIC_DIR="$HOME/../x"\n')
        dirs = wi.user_dirs(home)
        self.assertEqual(dirs["documents"], home / "Documents")
        self.assertEqual(dirs["music"], home / "Music")


class Bookmarks(Base):
    def test_linux_browsers_native_flatpak_snap(self):
        home = self.tmp / "home" / "anna"
        chrome = {"roots": {"bookmark_bar": {"name": "Bar", "children": [
            {"type": "url", "name": "Sloth", "url": "https://sloth-os-linux.github.io/"}]}}}
        touch(home / ".config/google-chrome/Default/Bookmarks", json.dumps(chrome))
        touch(home / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser/Default/Bookmarks",
              json.dumps(chrome))
        firefox_places(home / "snap/firefox/common/.mozilla/firefox/abc.default/places.sqlite",
                       "https://example.org/", "Example")
        folders = wi.bookmark_folders(home)
        self.assertEqual(sorted(f["title"] for f in folders), ["Brave", "Firefox", "Google Chrome"])
        self.assertEqual(wi.count_bookmarks(folders), 3)


class Partitions(Base):
    LSBLK = {"blockdevices": [
        {"path": "/dev/nvme0n1", "type": "disk", "size": 512 * 1024**3, "children": [
            {"path": "/dev/nvme0n1p1", "type": "part", "fstype": "vfat", "size": 600 * 1024**2,
             "mountpoints": ["/boot/efi"]},
            {"path": "/dev/nvme0n1p2", "type": "part", "fstype": "ext4", "size": 2 * 1024**3, "mountpoints": ["/boot"]},
            {"path": "/dev/nvme0n1p3", "type": "part", "fstype": "btrfs", "size": 200 * 1024**3,
             "mountpoints": ["/sysroot", "/var", "/var/home"]},
            {"path": "/dev/nvme0n1p4", "type": "part", "fstype": "ext4", "size": 100 * 1024**3,
             "mountpoints": [None]},
            {"path": "/dev/nvme0n1p5", "type": "part", "fstype": "ext4", "size": 50 * 1024**3,
             "mountpoints": ["/run/media/me/Ubuntu"]},
            {"path": "/dev/nvme0n1p6", "type": "part", "fstype": "ntfs", "size": 150 * 1024**3, "mountpoints": [None]},
        ]},
        {"path": "/dev/sda", "type": "disk", "size": 1024**4, "children": [
            {"path": "/dev/sda1", "type": "part", "fstype": "crypto_LUKS", "size": 500 * 1024**3,
             "mountpoints": [None]},
            {"path": "/dev/sda2", "type": "part", "fstype": "crypto_LUKS", "size": 400 * 1024**3,
             "mountpoints": [None], "children": [
                 {"path": "/dev/mapper/luks-x", "type": "crypt", "fstype": "btrfs", "size": 400 * 1024**3,
                  "mountpoints": ["/sysroot"]}]},
            {"path": "/dev/sda3", "type": "part", "fstype": "xfs", "size": 5 * 1024**3, "mountpoints": [None]},
        ]},
    ]}

    def test_candidates(self):
        out = mock.Mock(stdout=json.dumps(self.LSBLK))
        with mock.patch.object(wi.subprocess, "run", return_value=out):
            found = {c["device"]: c for c in wi.candidates()}
        self.assertEqual(sorted(found), ["/dev/nvme0n1p4", "/dev/nvme0n1p5", "/dev/nvme0n1p6", "/dev/sda1"])
        self.assertEqual(found["/dev/nvme0n1p4"]["kind"], "linux")
        self.assertFalse(found["/dev/nvme0n1p4"]["locked"])
        self.assertEqual(found["/dev/nvme0n1p6"]["kind"], "windows")
        self.assertTrue(found["/dev/sda1"]["locked"])          # another Linux's encrypted disk, not opened
        self.assertEqual(found["/dev/nvme0n1p4"]["fstype"], "ext4")

    def test_btrfs_mounted_at_its_top(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=0, stdout="/run/media/me/x\n" if cmd[0] == "findmnt" and len(calls) > 1 else "")
        with mock.patch.object(wi.subprocess, "run", side_effect=run):
            mnt, ours = wi.mount("/dev/nvme0n1p4", "btrfs")
        self.assertEqual((mnt, ours), ("/run/media/me/x", True))
        self.assertIn(["udisksctl", "mount", "-b", "/dev/nvme0n1p4", "-o", "ro,subvolid=5"], calls)


class SteamGames(Base):
    def setUp(self):
        super().setUp()
        self.mnt = self.tmp / "ubuntu"
        (self.mnt / "etc").mkdir(parents=True)
        home = self.mnt / "home" / "anna"
        touch(home / ".bashrc")
        apps = home / ".local/share/Steam/steamapps"
        touch(apps / "appmanifest_10.acf", manifest("10", "Native Game", "Native"))
        touch(apps / "common/Native/game.x86_64", b"elf")
        touch(apps / "appmanifest_20.acf", manifest("20", "Proton Game", "ProtonGame"))
        touch(apps / "common/ProtonGame/game.exe", b"exe!")
        touch(apps / "compatdata/20/pfx/drive_c/users/steamuser/Saved Games/save.dat", b"save")
        # a second library on another drive of the old system, named in libraryfolders.vdf
        touch(apps / "libraryfolders.vdf", '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"/home/anna/.local/share/Steam"\n'
                                           '\t}\n\t"1"\n\t{\n\t\t"path"\t\t"/mnt/games/SteamLibrary"\n\t}\n}\n')
        lib2 = self.mnt / "mnt/games/SteamLibrary/steamapps"
        touch(lib2 / "appmanifest_30.acf", manifest("30", "Far Game", "Far"))
        touch(lib2 / "common/Far/far.bin", b"far")
        # the Flatpak Steam's library too
        fl = home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
        touch(fl / "appmanifest_40.acf", manifest("40", "Flatpak Game", "Flat"))
        touch(fl / "common/Flat/f.bin", b"f")

    def test_found_with_proton_environments(self):
        games = {g["appid"]: g for g in wi.steam_games([str(self.mnt)])}
        self.assertEqual(sorted(games), ["10", "20", "30", "40"])
        self.assertFalse(games["10"]["proton"])
        self.assertEqual(games["10"]["compat"], "")
        self.assertTrue(games["20"]["proton"])
        self.assertEqual(Path(games["20"]["compat"]).parts[-2:], ("compatdata", "20"))
        self.assertEqual(games["20"]["size"], 4 + 4)            # the game and its Proton environment

    def test_copied_with_proton_environment(self):
        games = [g for g in wi.steam_games([str(self.mnt)]) if g["appid"] in ("10", "20")]
        lib = self.tmp / "here"
        stats = wi.copy_games(games, root=lib)
        self.assertEqual(stats["games"], 2)
        self.assertTrue((lib / "steamapps/compatdata/20/pfx/drive_c/users/steamuser/Saved Games/save.dat").is_file())
        self.assertTrue((lib / "steamapps/appmanifest_10.acf").is_file())
        self.assertFalse((lib / "steamapps/compatdata/10").exists())

    def test_proton_only_for_games_that_had_it(self):
        games = [g for g in wi.steam_games([str(self.mnt)]) if g["appid"] in ("10", "20")]
        lib = self.tmp / "here"
        wi.copy_games(games, root=lib)
        asked = []
        with mock.patch.object(wi, "has_linux_version", side_effect=lambda a: asked.append(a) or True), \
                mock.patch.object(wi, "force_proton", return_value=1) as fp:
            out = wi.finish_games(games, None, root=lib, library=lib)
        self.assertEqual(asked, ["20"])          # the native game keeps its Linux version
        fp.assert_called_once_with(lib, ["20"])
        self.assertEqual(out["saves"], [])       # Windows' save places: not looked for without a Windows home


class Copying(Base):
    def test_localised_folders_and_linux_suffix(self):
        home = self.tmp / "home" / "anna"
        touch(home / ".config/user-dirs.dirs", USER_DIRS_HU)
        touch(home / "Dokumentumok/levél.odt", b"new contents")
        touch(home / "Dokumentumok/same.txt", b"same")
        dest = self.tmp / "Documents here"
        touch(dest / "levél.odt", b"an older, longer file")
        touch(dest / "same.txt", b"same")
        with mock.patch.object(wi, "target_dir", return_value=dest):
            stats = wi.copy(home, ["documents"], dirs={k: str(v) for k, v in wi.user_dirs(home).items()},
                            label="Linux")
        self.assertEqual((stats["copied"], stats["skipped"]), (1, 1))
        self.assertEqual((dest / "levél (Linux).odt").read_bytes(), b"new contents")
        # again: nothing new
        with mock.patch.object(wi, "target_dir", return_value=dest):
            again = wi.copy(home, ["documents"], dirs={k: str(v) for k, v in wi.user_dirs(home).items()},
                            label="Linux")
        self.assertEqual((again["copied"], again["skipped"]), (0, 2))

    def test_several_localised_folders_at_once(self):
        # every folder by its own localised name, not only the first one (the walk once overwrote the folder list)
        home = self.tmp / "home" / "anna"
        touch(home / ".config/user-dirs.dirs", USER_DIRS_HU)
        touch(home / "Dokumentumok/a.txt", b"a")
        touch(home / "Asztal/b.png", b"bb")
        touch(home / "Képek/c.jpg", b"ccc")
        here = self.tmp / "here"
        with mock.patch.object(wi, "target_dir", side_effect=lambda k: here / k):
            stats = wi.copy(home, ["documents", "desktop", "pictures"],
                            dirs={k: str(v) for k, v in wi.user_dirs(home).items()}, label="Linux")
        self.assertEqual(stats["copied"], 3)
        self.assertEqual(sorted(p.relative_to(here).as_posix() for p in here.rglob("*") if p.is_file()),
                         ["desktop/b.png", "documents/a.txt", "pictures/c.jpg"])


if __name__ == "__main__":
    unittest.main()
