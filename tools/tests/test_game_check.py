#!/usr/bin/env python3
"""The "Will it run?" check (sloth_common/game_check.py) on a small made-up game list; no network or Qt.
With a games-index.json path as the argument it also searches a real list: test_game_check.py <file> "witcher 3"."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import game_check as gc  # noqa: E402

GAMES = {
    "steam:1172470": {"n": "Apex Legends", "r": "poor", "t": 424, "w": 0, "a": "denied",
                      "ac": ["Easy Anti-Cheat", "Hyperion"], "p": "Electronic Arts"},
    "steam:1091500": {"n": "Cyberpunk 2077", "r": "great", "t": 757, "w": 93,
                      "g": {"amd": 95, "nvidia": 91, "intel": 86}},
    "steam:292030": {"n": "The Witcher 3: Wild Hunt", "r": "great", "t": 339, "w": 88},
    "steam:20900": {"n": "The Witcher: Enhanced Edition", "r": "ok", "t": 20, "w": 70},
    "steam:359550": {"n": "Tom Clancy's Rainbow Six® Siege", "r": "poor", "t": 96, "w": 11, "a": "denied"},
    "steam:570": {"n": "Dota 2", "r": "ok", "t": 141, "w": 83, "l": 1},
    "steam:1": {"n": "Some Broken Shooter", "r": "", "t": 1, "w": 0, "a": "broken", "ac": ["Vanguard"]},
    "awacy:valorant": {"n": "VALORANT", "r": "", "t": 0, "a": "denied", "ac": ["Vanguard"]},
    "steam:2": {"n": "Tiny Indie", "r": "", "t": 2, "w": 100},
    "awacy:roblox": {"n": "Roblox", "r": "", "t": 0, "a": "denied", "ac": ["Hyperion"], "p": "Roblox"},
    "steam:1245620": {"n": "ELDEN RING", "r": "great", "t": 387, "w": 94, "st": "works", "sd": "2026-10-28"},
}


class GameCheckTest(unittest.TestCase):
    def names(self, query):
        return [v["name"] for v in gc.search(GAMES, query)]

    def test_search_ignores_case_accents_and_punctuation(self):
        self.assertEqual(self.names("witcher 3")[0], "The Witcher 3: Wild Hunt")
        self.assertEqual(self.names("rainbow six")[0], "Tom Clancy's Rainbow Six® Siege")
        self.assertEqual(self.names("tom clancys"), ["Tom Clancy's Rainbow Six® Siege"])
        self.assertEqual(self.names("CYBERPUNK"), ["Cyberpunk 2077"])
        self.assertEqual(self.names("x"), [])
        # the same with the names made once in advance
        self.assertEqual([v["name"] for v in gc.search(GAMES, "witcher 3", names=gc.index_names(GAMES))][0],
                         "The Witcher 3: Wild Hunt")
        self.assertEqual(self.names("nothing like this"), [])

    def test_order_exact_then_start_then_words(self):
        # "witcher": both Witchers contain it; the one with more reports first
        self.assertEqual(self.names("witcher"), ["The Witcher 3: Wild Hunt", "The Witcher: Enhanced Edition"])
        self.assertEqual(self.names("valorant"), ["VALORANT"])

    def test_verdicts(self):
        apex = gc.search(GAMES, "apex")[0]
        self.assertEqual((apex["badge"], apex["anticheat"]), ("blocked", ["Easy Anti-Cheat", "Hyperion"]))
        # whom to ask, and where the verdict comes from (the team did not try them all)
        self.assertEqual(apex["publisher"], "Electronic Arts")
        self.assertEqual(apex["sources"], ["ProtonDB", "AreWeAntiCheatYet"])
        self.assertEqual(gc.search(GAMES, "valorant")[0]["sources"], ["AreWeAntiCheatYet"])
        self.assertEqual(gc.lookup(GAMES, "1245620")["sources"], ["ProtonDB", "Sloth OS"])
        self.assertEqual(gc.lookup(GAMES, "1091500")["sources"], ["ProtonDB"])
        self.assertEqual(gc.search(GAMES, "broken shooter")[0]["badge"], "broken")
        cp = gc.lookup(GAMES, "1091500", known={"1091500"})
        self.assertEqual((cp["badge"], cp["works"], cp["reports"], cp["known"]), ("great", 93, 757, True))
        self.assertEqual(cp["gpus"], [("AMD", 95), ("NVIDIA", 91), ("Intel", 86)])
        self.assertTrue(gc.lookup(GAMES, "570")["native"])
        self.assertEqual(gc.lookup(GAMES, "2")["badge"], "unknown")
        elden = gc.lookup(GAMES, "1245620")
        self.assertEqual((elden["badge"], elden["tested"]), ("tested", "works"))
        self.assertEqual(gc.search(GAMES, "valorant")[0]["works"], -1)  # no reports at all
        self.assertIsNone(gc.lookup(GAMES, "999"))

    def test_community_alternative(self):
        """Roblox blocks its Windows version, but Sober runs it: that is the answer (a Reddit comment, 2026-10-29)."""
        roblox = gc.search(GAMES, "roblox")[0]
        self.assertEqual((roblox["badge"], roblox["alternative"]), ("alternative", "Sober"))
        self.assertEqual(gc.search(GAMES, "apex")[0]["alternative"], "")

    def test_cache_and_known_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "games-index.json"
            self.assertTrue(gc.needs_download(cache))
            self.assertEqual(gc.load(cache), {})
            cache.write_text(json.dumps({"version": 1, "games": GAMES}))
            self.assertFalse(gc.needs_download(cache))
            self.assertTrue(gc.needs_download(cache, now=time.time() + gc.MAX_AGE_S + 60))
            self.assertEqual(len(gc.load(cache)), len(GAMES))
            knowledge = Path(tmp) / "knowledge.json"
            knowledge.write_text(json.dumps({"games": {"umu-1091500": {}, "umu-570": {}}, "programs": {}}))
            self.assertEqual(gc.known_settings(knowledge), {"1091500", "570"})
            self.assertEqual(gc.known_settings(Path(tmp) / "missing.json"), set())


if __name__ == "__main__":
    if len(sys.argv) > 2:
        games = gc.load(sys.argv[1])
        for v in gc.search(games, " ".join(sys.argv[2:])):
            print(v["badge"], v["works"], v["reports"], v["name"], v["anticheat"])
    else:
        unittest.main(verbosity=2)
