"""Quiet hours: no notification asks for a restart in this part of the day (Sloth Center → Updates).

The notifications that ask for a restart (a system update is ready, the NVIDIA driver is ready) call defer() first:
in the quiet hours they do not speak, but come back by themselves when the quiet hours end (a one-time user timer
runs the same notification again). Nothing is lost and nothing restarts on its own: the update waits for the next
restart anyway. The times are to the minute ("22:30"), the period may go over midnight (22:30 to 7:15). Inside, a
time is minutes after midnight; the file has "HH:MM", and a whole hour as a number (as the first version saved it)
is still read.
"""
import datetime
import json
import os
import re
import subprocess
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "quiet-hours.json"
DEFAULTS = {"enabled": False, "start": 22 * 60, "end": 7 * 60}
DAY = 24 * 60


def minutes(value):
    """"22:30" (or a whole hour as a number) -> minutes after midnight, or None if it is not a time."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value * 60 if 0 <= value <= 23 else None
    if isinstance(value, str):
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
        if m and int(m[1]) <= 23 and int(m[2]) <= 59:
            return int(m[1]) * 60 + int(m[2])
    return None


def clock(value):
    """Minutes after midnight -> "HH:MM"."""
    return f"{value // 60:02d}:{value % 60:02d}"


def load(path=None):
    try:
        data = json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    cfg = dict(DEFAULTS)
    if isinstance(data, dict):
        if isinstance(data.get("enabled"), bool):
            cfg["enabled"] = data["enabled"]
        for key in ("start", "end"):
            value = minutes(data.get(key))
            if value is not None:
                cfg[key] = value
    return cfg


def save(cfg, path=None):
    path = Path(path or CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"enabled": bool(cfg["enabled"]), "start": clock(cfg["start"] % DAY), "end": clock(cfg["end"] % DAY)}
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def is_quiet(cfg, now=None):
    if not cfg.get("enabled") or cfg["start"] == cfg["end"]:
        return False
    now = now or datetime.datetime.now()
    m = now.hour * 60 + now.minute
    if cfg["start"] < cfg["end"]:
        return cfg["start"] <= m < cfg["end"]
    return m >= cfg["start"] or m < cfg["end"]   # over midnight


def seconds_left(cfg, now=None):
    """Seconds until the quiet hours end (they are on now)."""
    now = now or datetime.datetime.now()
    end = now.replace(hour=cfg["end"] // 60, minute=cfg["end"] % 60, second=0, microsecond=0)
    if end <= now:
        end += datetime.timedelta(days=1)
    return int((end - now).total_seconds())


def defer(module, now=None, path=None):
    """In the quiet hours: runs `python3 -m <module>` again when they end, and returns True (the caller stays
    silent). Otherwise False. One timer per notification: a second call meanwhile changes nothing."""
    cfg = load(path)
    if not is_quiet(cfg, now):
        return False
    unit = "sloth-quiet-" + module.rsplit(".", 1)[-1].replace("_", "-")
    try:
        subprocess.run(["systemd-run", "--user", "--collect", f"--unit={unit}",
                        f"--on-active={seconds_left(cfg, now) + 60}",
                        "--setenv=PYTHONPATH=/usr/lib/sloth-os/sloth-center:/usr/lib/sloth-os/common",
                        "/usr/bin/python3", "-m", module],
                       capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass
    return True
