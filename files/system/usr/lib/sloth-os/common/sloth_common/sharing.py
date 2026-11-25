"""The settings for sharing with the shared knowledge (both off by default).

- share: Windows programs (Sloth Center → Windows programs, Sloth Welcome's question): the .exe handler
  (sloth_exe/community.py) may send anonymous reports, the program by a fingerprint of its name.
- share_games: Steam games (Sloth Center → Games): what fixed a game (sloth_common/steam_doctor.py). A separate yes,
  because the game is known by its public Steam number, which anyone can look up (the Windows programs' promise,
  "the name cannot be recovered", would not hold). Its reports wait in their own queue.
"""
import json
import os
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "community.json"
QUEUE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "community-queue.jsonl"
GAMES_QUEUE = QUEUE.with_name("community-games-queue.jsonl")


def _get(key):
    try:
        return bool(json.loads(CONFIG.read_text(encoding="utf-8")).get(key))
    except (OSError, ValueError, AttributeError):
        return False


def _set(key, value, queue):
    data = {}
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    data[key] = bool(value)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not value:
        queue.unlink(missing_ok=True)  # turning it off deletes the reports not sent yet too


def enabled():
    return _get("share")


def set_enabled(value):
    _set("share", value, QUEUE)


def games_enabled():
    return _get("share_games")


def set_games_enabled(value):
    _set("share_games", value, GAMES_QUEUE)
