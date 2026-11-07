#!/usr/bin/env python3
"""The game saves backup (/usr/libexec/sloth-os/game-saves) without Ludusavi: the config file it writes for a made-up
home folder, and how it reads Ludusavi's --api output (the shapes from Ludusavi 0.31's docs/schema/general-output.yaml
and docs/help/command-line.md)."""
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("game_saves", str(REPO / "files/system/usr/libexec/sloth-os/game-saves"))
spec = importlib.util.spec_from_loader(loader.name, loader)
gs = importlib.util.module_from_spec(spec)
loader.exec_module(gs)


class Config(unittest.TestCase):
    def test_roots_that_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".var/app/com.valvesoftware.Steam/.local/share/Steam").mkdir(parents=True)
            (home / ".var/app/com.heroicgameslauncher.hgl/config/heroic").mkdir(parents=True)
            (home / "Applications/Battle.net/windows/drive_c").mkdir(parents=True)
            self.assertEqual(gs.roots(home), [
                (str(home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"), "steam"),
                (str(home / ".var/app/com.heroicgameslauncher.hgl/config/heroic"), "heroic"),
                (str(home / "Applications/*/windows"), "otherWine")])

    def test_config_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "Kis Péter"   # spaces and accents stay one quoted string
            (home / ".steam/steam").mkdir(parents=True)
            text = gs.config_text(home, home / ".local/share/sloth-os/game-saves")
            self.assertIn(f'  - path: "{home}/.steam/steam"\n    store: steam', text)
            self.assertIn(f'backup:\n  path: "{home}/.local/share/sloth-os/game-saves"', text)
            self.assertIn("restore:\n  path:", text)
            self.assertNotIn("roots: []", text)

    def test_no_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("roots: []", gs.config_text(Path(tmp), Path(tmp) / "b"))


class Output(unittest.TestCase):
    BACKUP = {  # backup --force --api (the example of docs/help/command-line.md)
        "errors": {"someGamesFailed": True},
        "overall": {"totalGames": 2, "totalBytes": 150, "processedGames": 1, "processedBytes": 100},
        "games": {
            "Game 1": {"decision": "Processed", "change": "Different",
                       "files": {"/games/game1/save.json": {"bytes": 100}, "/games/game1/b.sav": {"bytes": 20}},
                       "registry": {"HKEY_CURRENT_USER/Software/Game1": {"failed": True}}},
            "Game 2": {"decision": "Ignored", "files": {"/games/game2/save.json": {"bytes": 50}}, "registry": {}},
        }}
    BACKUPS = {  # backups --api: ApiGame's second form (backupPath, backups: [ApiBackup])
        "games": {
            "Hollow Knight": {"backupPath": "/b/Hollow Knight", "backups": [
                {"name": ".", "when": "2026-11-06T18:00:00Z", "locked": False},
                {"name": "backup-20261107T100000Z-diff", "when": "2026-11-07T10:00:00Z", "locked": False}]},
            "Empty": {"backupPath": "/b/Empty", "backups": []},
        }}

    def test_summary(self):
        s = gs.summarize(self.BACKUP, when=1000)
        self.assertEqual(s, {"when": 1000, "games": {"Game 1": 120}, "failed": True})  # ignored games are not listed
        self.assertEqual(gs.summarize(None, when=5), {"when": 5, "games": {}, "failed": False})

    def test_backups(self):
        self.assertEqual(gs.backups(self.BACKUPS),
                         {"Hollow Knight": {"when": "2026-11-07T10:00:00Z", "count": 2}})
        self.assertEqual(gs.backups({}), {})
        json.dumps(gs.backups(self.BACKUPS))  # what `game-saves list` prints


if __name__ == "__main__":
    unittest.main(verbosity=2)
