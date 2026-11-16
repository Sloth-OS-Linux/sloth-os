#!/usr/bin/env python3
"""The game library (sloth_common/game_library.py): Steam's covers in both cache layouts, Heroic's games, the
Windows games' Steam covers, image sizes and the start commands. Temporary folders, no network."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import game_library as gl  # noqa: E402


def png(path, w, h):
    """A tiny valid PNG of the given size (only its header matters here)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\x00" * w * 3 for _ in range(h))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def jpeg(path, w, h):
    """A JPEG header with its frame size (SOF0), enough for image_size()."""
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9 + sof
                           + b"\xff\xd9")


class Sizes(unittest.TestCase):
    def test_image_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            png(Path(tmp, "a.png"), 6, 9)
            jpeg(Path(tmp, "b.jpg"), 600, 900)
            Path(tmp, "c.txt").write_text("no image")
            self.assertEqual(gl.image_size(Path(tmp, "a.png")), (6, 9))
            self.assertEqual(gl.image_size(Path(tmp, "b.jpg")), (600, 900))
            self.assertIsNone(gl.image_size(Path(tmp, "c.txt")))
            self.assertIsNone(gl.image_size(Path(tmp, "missing.jpg")))


class SteamCovers(unittest.TestCase):
    def test_both_layouts(self):
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root, "appcache/librarycache")
            # before 2026: one flat file per game
            jpeg(cache / "10_library_600x900.jpg", 600, 900)
            self.assertTrue(gl.steam_cover(root, "10").endswith("10_library_600x900.jpg"))
            # a folder per game, the old name inside a hashed folder
            jpeg(cache / "20/1159a696/library_600x900.jpg", 600, 900)
            jpeg(cache / "20/1159a696/library_header.jpg", 460, 215)
            self.assertTrue(gl.steam_cover(root, "20").endswith("1159a696/library_600x900.jpg"))
            # hashed names only: the portrait one is the cover, not the wide header or hero
            jpeg(cache / "30/7b45d809.jpg", 920, 430)
            jpeg(cache / "30/a1b2c3d4.jpg", 600, 900)
            jpeg(cache / "30/e5f6a7b8.jpg", 3840, 1240)
            self.assertTrue(gl.steam_cover(root, "30").endswith("a1b2c3d4.jpg"))
            # nothing: "" (then the image server)
            jpeg(cache / "40/wide.jpg", 920, 430)
            self.assertEqual(gl.steam_cover(root, "40"), "")
            self.assertEqual(gl.steam_cover(root, "50"), "")

    def test_entry(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(gl, "CACHE", Path(root, "covers")):
            e = gl.steam_entry(root, "570", "Dota 2")
            self.assertEqual(e["launch"], ["xdg-open", "steam://rungameid/570"])
            self.assertEqual(e["cover"], "")
            self.assertTrue(all("/570/library_600x900.jpg" in u for u in e["remote"]))
            jpeg(Path(root, "appcache/librarycache/570_library_600x900.jpg"), 600, 900)
            self.assertEqual(gl.steam_entry(root, "570", "Dota 2")["remote"], [])


class Heroic(unittest.TestCase):
    def test_games(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.object(gl, "CACHE", Path(home, "covers")):
            self.assertEqual(gl.heroic_games(home), [])          # no Heroic
            h = Path(home, ".var/app/com.heroicgameslauncher.hgl/config/heroic")
            epic = h / "legendaryConfig/legendary"
            (epic / "metadata").mkdir(parents=True)
            (epic / "installed.json").write_text(json.dumps({"Quail": {"install_path": "/g/Quail"}}))
            (epic / "metadata/Quail.json").write_text(json.dumps({"metadata": {"title": "Quail Game", "keyImages": [
                {"type": "DieselGameBox", "url": "https://x/wide.jpg"},
                {"type": "DieselGameBoxTall", "url": "https://x/tall.jpg"}]}}))
            (h / "gog_store").mkdir()
            (h / "gog_store/installed.json").write_text(json.dumps(
                {"installed": [{"appName": "1207658924", "install_path": "/g/Unreal Tournament 2004"}, "junk"]}))
            (h / "nile_config/nile").mkdir(parents=True)
            (h / "nile_config/nile/installed.json").write_text("not json")
            games = {g["id"]: g for g in gl.heroic_games(home)}
            self.assertEqual(set(games), {"epic:Quail", "gog:1207658924"})
            self.assertEqual(games["epic:Quail"]["name"], "Quail Game")
            self.assertEqual(games["epic:Quail"]["remote"], ["https://x/tall.jpg"])
            self.assertEqual(games["epic:Quail"]["launch"],
                             ["xdg-open", "heroic://launch?appName=Quail&runner=legendary"])
            self.assertEqual(games["gog:1207658924"]["name"], "Unreal Tournament 2004")
            self.assertEqual(games["gog:1207658924"]["launch"],
                             ["xdg-open", "heroic://launch?appName=1207658924&runner=gog"])


class WindowsGames(unittest.TestCase):
    def test_steam_cover_for_a_recognized_game(self):
        self.assertTrue(all("/1145360/" in u for u in gl.windows_cover("umu-1145360")))
        self.assertEqual(gl.windows_cover("umu-default"), [])
        self.assertEqual(gl.windows_cover("umu-ea-app"), [])
        self.assertEqual(gl.windows_cover(""), [])


class Download(unittest.TestCase):
    def test_first_image_wins_and_nothing_else_is_kept(self):
        class Response:
            def __init__(self, status, ctype, data):
                self.status, self.headers, self.data = status, {"Content-Type": ctype}, data

            def read(self, n):
                return self.data[:n]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        answers = {"https://a/x.jpg": Response(200, "text/html", b"<html>" * 500),
                   "https://b/x.jpg": Response(200, "image/jpeg", b"\xff\xd8" + b"\x00" * 5000)}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(gl, "CACHE", Path(tmp)), \
                mock.patch("urllib.request.urlopen", lambda req, timeout: answers[req.full_url]):
            path = gl.download("steam:1", ["https://a/x.jpg", "https://b/x.jpg"])
            self.assertTrue(path.endswith("steam_1.jpg"))
            self.assertEqual(gl.cached_cover("steam:1"), path)
            self.assertEqual(gl.download("steam:2", ["https://a/x.jpg"]), "")
            self.assertEqual(gl.cached_cover("steam:2"), "")


if __name__ == "__main__":
    unittest.main()
