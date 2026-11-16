#!/usr/bin/env python3
"""Game mode (sloth_common/game_mode.py, /usr/libexec/sloth-os/game-mode): what counts as a game, the names, the
setting, the state, and the units' check while someone plays. A fake /proc in a temporary folder."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import game_mode as gm  # noqa: E402

loader = importlib.machinery.SourceFileLoader("game_mode_service",
                                              str(REPO / "files/system/usr/libexec/sloth-os/game-mode"))
spec = importlib.util.spec_from_loader(loader.name, loader)
service = importlib.util.module_from_spec(spec)
loader.exec_module(service)


def proc(root, pid, cmdline, environ=()):
    d = Path(root, str(pid))
    d.mkdir()
    (d / "cmdline").write_bytes("\0".join(cmdline).encode() + b"\0")
    (d / "environ").write_bytes("\0".join(environ).encode() + b"\0")


class WhatIsAGame(unittest.TestCase):
    def test_kinds(self):
        steam = ["/home/u/.local/share/Steam/ubuntu12_32/reaper", "SteamLaunch", "AppId=1091500", "--", "x"]
        self.assertEqual(gm.game_of(steam, []), ("steam", "1091500"))
        self.assertIsNone(gm.game_of(["reaper", "SteamLaunch", "AppId=0"], []))       # Steam's own helper
        self.assertIsNone(gm.game_of(["/usr/bin/steam", "-silent"], []))              # Steam itself
        self.assertEqual(gm.game_of(["wine", "C:\\Games\\w3.exe"], ["HOME=/h", "GAMEID=umu-292030"]),
                         ("umu", "umu-292030"))
        # a Windows program nothing is known about, or not run by umu: not a game
        self.assertIsNone(gm.game_of(["wine", "notepad++.exe"], ["GAMEID=umu-default"]))
        self.assertIsNone(gm.game_of(["wine", "x.exe"], ["GAMEID=0"]))
        self.assertIsNone(gm.game_of(["firefox"], ["HOME=/h"]))
        # Steam preparing the game's shaders under the same reaper: not the game
        self.assertIsNone(gm.game_of(["reaper", "SteamLaunch", "AppId=1145360", "--",
                                     "/home/u/.local/share/Steam/ubuntu12_64/fossilize_replay", "x.foz"], []))

    def test_program_name(self):
        self.assertEqual(gm.program_name(["wine", "C:\\Games\\The Witcher 3\\bin\\x64\\witcher3.exe", "-x"]),
                         "witcher3")
        self.assertEqual(gm.program_name(["/usr/bin/foo"]), "")


class FindGames(unittest.TestCase):
    def test_find(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, home = Path(tmp, "proc"), Path(tmp, "home")
            root.mkdir()
            lib = home / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"
            lib.mkdir(parents=True)
            (lib / "appmanifest_1091500.acf").write_text(
                '"AppState"\n{\n\t"appid"\t\t"1091500"\n\t"name"\t\t"Cyberpunk 2077"\n}\n')
            proc(root, 4100, ["reaper", "SteamLaunch", "AppId=1091500", "--", "game"])
            proc(root, 4101, ["Cyberpunk2077.exe"], ["SteamAppId=1091500"])
            proc(root, 4200, ["wine", "C:\\x\\Hades.exe"], ["GAMEID=umu-1145360"])
            proc(root, 4201, ["wine", "C:\\x\\Hades.exe"], ["GAMEID=umu-1145360"])
            proc(root, 4300, ["wine", "C:\\x\\tool.exe"], ["GAMEID=umu-default"])
            proc(root, 4400, ["plasmashell"])
            Path(root, "self").mkdir()
            games = gm.find_games(str(root), uid=os.getuid(), home=home)
            self.assertEqual(set(games), {("steam", "1091500"), ("umu", "umu-1145360")})
            self.assertEqual(games[("steam", "1091500")], {"pids": [4100], "name": "Cyberpunk 2077"})
            self.assertEqual(games[("umu", "umu-1145360")], {"pids": [4200, 4201], "name": "Hades"})

    def test_someone_elses_processes_are_not_looked_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc(tmp, 4100, ["reaper", "SteamLaunch", "AppId=10"])
            self.assertEqual(gm.find_games(tmp, uid=os.getuid() + 1), {})


class SettingAndState(unittest.TestCase):
    def test_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "sloth-os/game-mode.json")
            self.assertEqual(gm.load(path), {"enabled": True})     # on by default
            gm.save(False, path)
            self.assertEqual(gm.load(path), {"enabled": False})
            path.write_text("not json")
            self.assertEqual(gm.load(path), {"enabled": True})

    def test_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "sloth-os/gaming")
            self.assertIsNone(gm.read_state(path))
            gm.write_state(["Hades"], path, now=100)
            self.assertEqual(gm.read_state(path), {"name": "Hades", "since": 100})
            gm.clear_state(path)
            self.assertIsNone(gm.read_state(path))

    def test_anyone_playing(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "1000/sloth-os").mkdir(parents=True)
            Path(tmp, "1001").mkdir()
            self.assertFalse(gm.anyone_playing(tmp))
            Path(tmp, "1000/sloth-os/gaming").write_text("{}")
            self.assertTrue(gm.anyone_playing(tmp))

    def test_on_mains(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(gm.on_mains(tmp))                       # a desktop: no battery
            for name, kind, extra in (("BAT0", "Battery", {}), ("AC", "Mains", {"online": "0"}),
                                      ("hid-mouse", "Battery", {"scope": "Device"})):
                d = Path(tmp, name)
                d.mkdir()
                (d / "type").write_text(kind + "\n")
                for k, v in extra.items():
                    (d / k).write_text(v + "\n")
            self.assertFalse(gm.on_mains(tmp))                      # a laptop on battery
            Path(tmp, "AC/online").write_text("1\n")
            self.assertTrue(gm.on_mains(tmp))


class UnitsWait(unittest.TestCase):
    """ExecCondition=game-mode playing [UNIT]: 1 skips the job while a game runs, and a user unit is noted."""

    def test_playing(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, skipped = Path(tmp, "gaming"), Path(tmp, "skipped")
            with mock.patch.object(gm, "STATE", state), mock.patch.object(gm, "SKIPPED", skipped), \
                    mock.patch.object(service.os, "geteuid", return_value=1000):
                self.assertEqual(service.playing("sloth-game-saves.service"), 0)
                self.assertFalse(skipped.exists())
                gm.write_state(["Hades"], state)
                self.assertEqual(service.playing("sloth-game-saves.service"), 1)
                self.assertEqual(skipped.read_text().split(), ["sloth-game-saves.service"])

    def test_a_fault_never_stops_the_jobs(self):
        with mock.patch.object(service.gm, "read_state", side_effect=RuntimeError("broken")), \
                mock.patch.object(service.os, "geteuid", return_value=1000):
            self.assertEqual(service.playing("sloth-game-saves.service"), 0)
        with mock.patch.object(service, "gm", None):
            self.assertEqual(service.playing(""), 0)

    def test_a_quick_close_counts_only_if_the_game_does_not_come_back(self):
        mode = service.GameMode.__new__(service.GameMode)     # without D-Bus: only the bookkeeping
        mode.started, mode.suspects, mode.failed = {}, {}, []
        seen = []
        mode.record = lambda appid, name, seconds: seen.append((appid, round(seconds)))
        key = ("steam", "10")
        game = {key: {"name": "Game", "pids": [1]}}
        # a launcher: 5 s, then the game comes back 20 s later and runs: no failure
        mode.watch_runs(game, 0)
        mode.watch_runs({}, 5)
        mode.watch_runs(game, 25)
        mode.watch_runs({}, 1000)
        self.assertEqual(seen, [("10", 975)])
        # a real quick close: 4 s, and nothing for 90 s: a failure
        seen.clear()
        mode.watch_runs(game, 2000)
        mode.watch_runs({}, 2004)
        mode.watch_runs({}, 2050)
        self.assertEqual(seen, [])
        mode.watch_runs({}, 2100)
        self.assertEqual(seen, [("10", 4)])

    def test_skipped_jobs_run_after_the_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            skipped = Path(tmp, "skipped")
            skipped.write_text("sloth-game-saves.service\nsloth-game-saves.service\nsomething-else.service\n")
            with mock.patch.object(gm, "SKIPPED", skipped), mock.patch.object(service.subprocess, "run") as run:
                service.GameMode.run_skipped()
            self.assertEqual([c.args[0][-1] for c in run.call_args_list], ["sloth-game-saves.service"])
            self.assertFalse(skipped.exists())


if __name__ == "__main__":
    unittest.main()
