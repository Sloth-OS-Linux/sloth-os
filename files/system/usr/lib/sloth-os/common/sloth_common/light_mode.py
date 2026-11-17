"""Lighter mode for weak computers: no animations, no blur behind panels and menus, file search by name only.

Weak means (any of them): about 4 GB of memory or less, at most 2 processor threads, or no graphics driver that can
draw (no /dev/dri/renderD* node: everything is drawn by the processor). On such a computer it is turned on by itself
at the first sign-in (sloth_center.light_mode_auto, the user service sloth-light-mode.service), once: whatever the
user chooses later in Sloth Center (Appearance) stays.

What it changes, each one KDE's own setting (checked against Plasma 6.8's files, 2026-11-17):
  - kdeglobals [KDE] AnimationDurationFactor = 0: animations off (System Settings → Animation speed "Instant";
    kwin.kcfg / landingpage_kdeglobalssettings.kcfg)
  - kwinrc [Plugins] blurEnabled = false: KWin's blur effect off (the built-in effect "blur", kwin/src/plugins/blur)
  - Baloo: file content is not indexed, only names (`balooctl6 config set contentIndexing no`, which writes
    baloofilerc [General] "only basic indexing"); search still finds files by name
The values from before are kept, and turning it off puts them back (a key that was not there is deleted again).
"""
import json
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
STATE = CONFIG_HOME / "sloth-os" / "light-mode.json"
WEAK_MEMORY_KB = 4_700_000        # "4 GB" machines show about 3.6–3.9 GB in MemTotal; 6 GB ones about 5.6 GB
WEAK_THREADS = 2

# (file, group, key, the lighter value, type)
SETTINGS = (
    ("kdeglobals", "KDE", "AnimationDurationFactor", "0", None),
    ("kwinrc", "Plugins", "blurEnabled", "false", "bool"),
)


def _meminfo_kb(path="/proc/meminfo"):
    try:
        for line in Path(path).read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return 0


def reasons(meminfo="/proc/meminfo", dri="/dev/dri", threads=None):
    """Why this computer is weak: a list of "memory" / "processor" / "graphics", empty if it is not."""
    out = []
    mem = _meminfo_kb(meminfo)
    if 0 < mem < WEAK_MEMORY_KB:
        out.append("memory")
    n = threads if threads is not None else (len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity")
                                            else os.cpu_count() or 0)
    if 0 < n <= WEAK_THREADS:
        out.append("processor")
    try:
        render = any(p.name.startswith("renderD") for p in Path(dri).iterdir())
    except OSError:
        render = False
    if not render:
        out.append("graphics")
    return out


def load_state():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def is_on():
    return bool(load_state().get("on"))


def _read(file, group, key):
    """The key's value in the user's file, or None if it is not set there (kreadconfig6 cannot tell the two apart)."""
    path = CONFIG_HOME / file
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    current = None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1]
        elif current == group and "=" in s:
            k, v = s.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return None


def _write(file, group, key, value, kind):
    cmd = ["kwriteconfig6", "--file", file, "--group", group, "--key", key, "--notify"]
    if value is None:
        cmd.append("--delete")
    else:
        if kind:
            cmd += ["--type", kind]
        cmd.append(value)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)


def _kwin_reconfigure():
    """KWin reads its settings again (effects on or off at once)."""
    try:
        subprocess.run(["busctl", "--user", "call", "org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def _baloo_content(on):
    try:
        subprocess.run(["balooctl6", "config", "set", "contentIndexing", "yes" if on else "no"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def _baloo_content_now():
    """Whether Baloo indexes file content now (its default: yes)."""
    v = _read("baloofilerc", "General", "only basic indexing")
    return not (v or "").lower() == "true"


def set_on(on, auto=False):
    """Turns the lighter mode on or off. auto: by itself at the first sign-in (otherwise the user's choice).
    -> True if everything was written."""
    state = load_state()
    ok = True
    try:
        if on and not state.get("on"):
            # what was there before, to put it back later
            state["before"] = {f"{f}/{g}/{k}": _read(f, g, k) for f, g, k, _v, _t in SETTINGS}
            state["before"]["baloo/contentIndexing"] = _baloo_content_now()
            for f, g, k, v, t in SETTINGS:
                _write(f, g, k, v, t)
            _baloo_content(False)
        elif not on and state.get("on"):
            before = state.get("before", {})
            for f, g, k, _v, t in SETTINGS:
                _write(f, g, k, before.get(f"{f}/{g}/{k}"), t)
            _baloo_content(bool(before.get("baloo/contentIndexing", True)))
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("lighter mode: %s", e)
        ok = False
    _kwin_reconfigure()
    state["on"] = bool(on)
    state["decided"] = "auto" if auto else "user"
    _save_state(state)
    return ok
