"""The setting for sharing with the shared knowledge (Sloth Center → Windows programs; off by default).

The .exe handler (sloth_exe/community.py) learns from it whether it may send anonymous reports.
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
        QUEUE.unlink(missing_ok=True)  # turning it off deletes the reports not sent yet too
