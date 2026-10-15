"""A közös tudás megosztásának beállítása (Sloth Központ → Windows-programok; alapból kikapcsolva).

Az .exe kezelő (sloth_exe/community.py) ebből tudja, küldhet-e névtelen jelentést.
"""
import json
import os
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "community.json"
QUEUE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "community-queue.jsonl"


def enabled():
    try:
        return bool(json.loads(CONFIG.read_text(encoding="utf-8")).get("share"))
    except (OSError, ValueError):
        return False


def set_enabled(value):
    data = {}
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    data["share"] = bool(value)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if not value:
        QUEUE.unlink(missing_ok=True)  # kikapcsoláskor a még el nem küldött jelentések is törlődnek
