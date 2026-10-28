#!/usr/bin/env python3
"""Moving a Steam game to another library (sloth_common/apps/steam_library.py) on a made-up Steam folder; no Steam,
Flatpak or Qt needed. Both the rename (same file system) and the copy (another drive) are tested, and a failed
copy must leave the game where it was."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
# On disk, not in /tmp: that is often tmpfs, which the library (rightly) does not allow (SUPPORTED_FS)
_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
_CACHE.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="sloth-steam-move-", dir=_CACHE))
os.environ.update(HOME=str(TMP), XDG_DATA_HOME=str(TMP / ".local/share"), XDG_CONFIG_HOME=str(TMP / ".config"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common.apps import steam, steam_library  # noqa: E402

APPID = "1091500"
MANIFEST = f'''"AppState"
{{
\t"appid"\t\t"{APPID}"
\t"name"\t\t"Cyberpunk 2077"
\t"installdir"\t\t"Cyberpunk 2077"
\t"SizeOnDisk"\t\t"4096"
}}
'''


def make_steam(base):
    """A Steam folder with one game (files, Proton environment, shader cache) and a second, empty library."""
    root = base / "Steam"
    other = base / "drive2" / "SteamLibrary"
    (root / "steamapps").mkdir(parents=True)
    (root / "steamapps" / "libraryfolders.vdf").write_text(steam.vdf_dump({"libraryfolders": {
        "0": {"path": str(root), "label": "", "contentid": "11", "apps": {APPID: "4096", "228980": "1"}}}}) + "\n")
    (root / "steamapps" / f"appmanifest_{APPID}.acf").write_text(MANIFEST)
    game = root / "steamapps/common/Cyberpunk 2077"
    (game / "bin").mkdir(parents=True)
    (game / "bin/game.exe").write_bytes(b"MZ" + b"x" * 4000)
    save = root / f"steamapps/compatdata/{APPID}/pfx/drive_c/users/steamuser/Saved Games"
    save.mkdir(parents=True)
    (save / "save1.dat").write_text("level 42")
    # Proton environments have links: they must stay links
    (root / f"steamapps/compatdata/{APPID}/pfx/link").symlink_to("drive_c")
    (root / f"steamapps/shadercache/{APPID}").mkdir(parents=True)
    (root / f"steamapps/shadercache/{APPID}/cache.bin").write_bytes(b"s" * 100)
    other.parent.mkdir(parents=True)
    return root, other


class SteamMoveTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(dir=TMP))
        self.root, self.other = make_steam(self.base)
        patch = mock.patch.object(steam_library, "grant_access", return_value=True)
        self.grant = patch.start()
        self.addCleanup(patch.stop)

    def libraries(self):
        data = steam.vdf_load((self.root / "steamapps/libraryfolders.vdf").read_text())
        return {v["path"]: v.get("apps", {}) for v in data["libraryfolders"].values()}

    def check_moved(self, src, dst):
        self.assertFalse((src / f"steamapps/appmanifest_{APPID}.acf").exists())
        self.assertFalse((src / "steamapps/common/Cyberpunk 2077").exists())
        self.assertTrue((dst / f"steamapps/appmanifest_{APPID}.acf").is_file())
        self.assertEqual((dst / "steamapps/common/Cyberpunk 2077/bin/game.exe").stat().st_size, 4002)
        save = dst / f"steamapps/compatdata/{APPID}/pfx/drive_c/users/steamuser/Saved Games/save1.dat"
        self.assertEqual(save.read_text(), "level 42")
        self.assertTrue((dst / f"steamapps/compatdata/{APPID}/pfx/link").is_symlink())
        self.assertTrue((dst / f"steamapps/shadercache/{APPID}/cache.bin").is_file())
        self.assertEqual(steam_library.find_game(self.root, APPID)["library"], dst)

    def test_rename_on_the_same_drive(self):
        self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "")
        self.check_moved(self.root, self.other)
        libs = self.libraries()
        # listed under the new library with its size; the other game stays where it was
        self.assertEqual(libs[str(self.other)], {APPID: "4096"})
        self.assertEqual(libs[str(self.root)], {"228980": "1"})
        self.assertTrue((self.other / "libraryfolder.vdf").is_file())
        self.grant.assert_called_once()
        # and back again, into Steam's own folder
        self.assertEqual(steam_library.move_game(self.root, APPID, self.root), "")
        self.check_moved(self.other, self.root)
        self.assertEqual(self.libraries()[str(self.root)], {"228980": "1", APPID: "4096"})

    def test_copy_to_another_drive(self):
        with mock.patch.object(steam_library.library, "_same_filesystem", return_value=False):
            self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "")
        self.check_moved(self.root, self.other)
        self.assertFalse(list(self.other.rglob("*" + steam_library.PARTIAL)))
        self.assertTrue((self.root / "steamapps/libraryfolders.vdf.sloth-backup").is_file())

    def test_failed_copy_leaves_the_game_alone(self):
        real_run = subprocess.run
        calls = []

        def fail_second(cmd, **kw):
            # the game's files are copied, then copying the Proton environment fails
            if cmd[0] == "cp":
                calls.append(cmd)
                if len(calls) == 2:
                    raise subprocess.CalledProcessError(1, cmd)
            return real_run(cmd, **kw)
        with mock.patch.object(steam_library.library, "_same_filesystem", return_value=False), \
                mock.patch.object(steam_library.subprocess, "run", side_effect=fail_second):
            self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "copy_failed")
        self.assertEqual(len(calls), 2)
        self.assertIn("compatdata", calls[1][-1])
        # everything still in the old place, nothing half-copied left behind, Steam's list unchanged
        self.assertEqual(steam_library.find_game(self.root, APPID)["library"], self.root)
        self.assertTrue((self.root / "steamapps/common/Cyberpunk 2077/bin/game.exe").is_file())
        self.assertFalse((self.other / "steamapps/common/Cyberpunk 2077").exists())
        self.assertFalse(list(self.other.rglob("*" + steam_library.PARTIAL)))
        self.assertEqual(self.libraries()[str(self.root)], {APPID: "4096", "228980": "1"})

    def test_refusals(self):
        self.assertEqual(steam_library.move_game(self.root, "999", self.other), "not_found")
        self.assertEqual(steam_library.move_game(self.root, APPID, self.root), "same_place")
        (self.other / "steamapps/common/Cyberpunk 2077").mkdir(parents=True)
        self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "exists")
        self.grant.return_value = False
        (self.other / "steamapps/common/Cyberpunk 2077").rmdir()
        self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "no_access")
        self.assertEqual(steam_library.find_game(self.root, APPID)["library"], self.root)

    def test_library_is_listed_once(self):
        steam_library.ensure_library(self.root, self.other)
        steam_library.ensure_library(self.root, self.other)
        self.assertEqual(list(self.libraries()), [str(self.root), str(self.other)])

    def test_bad_installdir_is_ignored(self):
        """A manifest pointing outside the library is never followed (nothing outside it may be moved or deleted)."""
        bad = MANIFEST.replace('"installdir"\t\t"Cyberpunk 2077"', '"installdir"\t\t"../.."')
        self.assertIn("../..", bad)
        (self.root / f"steamapps/appmanifest_{APPID}.acf").write_text(bad)
        self.assertIsNone(steam_library.find_game(self.root, APPID))
        self.assertEqual(steam_library.move_game(self.root, APPID, self.other), "not_found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
