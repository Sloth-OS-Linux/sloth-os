"""The "Will it run?" check (Sloth Center → Games): how well a game runs, from the game list of the shared knowledge
repository (games-index.json: ProtonDB reports, AreWeAntiCheatYet, the Sloth OS team's own tests; made monthly by
its seed/games_index.py). The list is downloaded in the background and kept, so the search works offline too.

The verdict, most important first:
  blocked  the makers don't allow it on Linux (the anti-cheat refuses it; AreWeAntiCheatYet "Denied")
  broken   its anti-cheat does not work on Linux (AreWeAntiCheatYet "Broken")
  tested   the Sloth OS team tried it (the result says how it went)
  great / ok / poor   from the reports: at least 85% / at least half / fewer say it works
  unknown  too few reports
"""
import json
import os
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/Sloth-OS-Linux/sloth-os-knowledge/main/games-index.json"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "games-index.json"
# The shared knowledge (downloaded by sloth-windows-prepare): games with a known working setting ("umu-<appid>")
KNOWLEDGE = CACHE.with_name("knowledge.json")
MAX_AGE_S = 7 * 86400
TIMEOUT_S = 30
GPU_NAMES = {"amd": "AMD", "nvidia": "NVIDIA", "intel": "Intel"}


def normalize(text):
    """For searching: lower case, no accents, no ™ ® or punctuation ("Tom Clancy's" = "tom clancys")."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"['’`]", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load(path=CACHE):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    games = data.get("games") if isinstance(data, dict) else None
    return games if isinstance(games, dict) else {}


def needs_download(path=CACHE, now=None):
    try:
        return (now or time.time()) - Path(path).stat().st_mtime > MAX_AGE_S
    except OSError:
        return True


def download(path=CACHE):
    """Downloads the list; the old one stays if this fails. -> True if a new list was saved."""
    path = Path(path)
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Sloth OS"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read()
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("games"), dict) or len(data["games"]) < 100:
            return False
    except (OSError, ValueError):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)
    return True


def known_settings(path=KNOWLEDGE):
    """The Steam AppIDs with a working setting in the shared knowledge (Sloth OS applies it by itself)."""
    try:
        games = json.loads(Path(path).read_text(encoding="utf-8")).get("games", {})
    except (OSError, ValueError, AttributeError):
        return set()
    return {k[4:] for k in games if isinstance(k, str) and k.startswith("umu-")}


def verdict(key, entry, known=()):
    """What the page shows about one game:
    {"key", "name", "badge", "works", "reports", "native", "gpus" [(name, %)], "anticheat" [..], "tested", "known"}"""
    if entry.get("a") == "denied":
        badge = "blocked"
    elif entry.get("a") == "broken":
        badge = "broken"
    elif entry.get("st"):
        badge = "tested"
    else:
        badge = entry.get("r") or "unknown"
    appid = key.split(":", 1)[1] if key.startswith("steam:") else ""
    return {
        "key": key,
        "name": entry.get("n", ""),
        "badge": badge,
        "works": entry.get("w", 0) if entry.get("t") else -1,
        "reports": entry.get("t", 0),
        "native": bool(entry.get("l")),
        "gpus": [(GPU_NAMES[g], p) for g, p in (entry.get("g") or {}).items() if g in GPU_NAMES],
        "anticheat": list(entry.get("ac") or []),
        "tested": entry.get("st", ""),
        "known": bool(appid) and appid in known,
    }


def index_names(games):
    """The searchable form of every name, made once (the list has ~20 000 games; search runs at every key press)."""
    return {key: normalize(entry.get("n", "")) for key, entry in games.items()}


def search(games, query, known=(), limit=15, names=None):
    """The games whose name matches: the exact name first, then the ones starting with it, then the ones containing
    every word; more reports first within each (the well-known game before a fan remake). names: index_names()."""
    q = normalize(query)
    if len(q) < 2:
        return []
    words = q.split()
    found = []
    for key, entry in games.items():
        name = names[key] if names is not None and key in names else normalize(entry.get("n", ""))
        if name == q:
            rank = 0
        elif name.startswith(q):
            rank = 1
        elif all(w in name.split() or any(part.startswith(w) for part in name.split()) for w in words):
            rank = 2
        else:
            continue
        found.append((rank, -entry.get("t", 0), name, key))
    found.sort()
    return [verdict(key, games[key], known) for _r, _t, _n, key in found[:limit]]


def lookup(games, appid, known=()):
    """The verdict of an installed Steam game, or None."""
    entry = games.get(f"steam:{appid}")
    return verdict(f"steam:{appid}", entry, known) if entry else None
