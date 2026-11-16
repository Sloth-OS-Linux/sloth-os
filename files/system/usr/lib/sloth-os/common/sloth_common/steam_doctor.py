"""What's wrong with the game? (Sloth Center → Games, a game's settings; the game-mode service notices.)

A Steam game that closes within QUICK_S seconds of starting most likely did not start. The game-mode service
(/usr/libexec/sloth-os/game-mode) records it here and says so in a notification; Sloth Center shows a readable summary
and tries one fix after the other, the same way the .exe handler heals Windows programs (sloth-exe/heal.py):
  1. without fsync/esync (a speed-up some games do not take),
  2. the older, OpenGL-based Direct3D (when the Vulkan path does not start),
  3. Proton Experimental (the newest one Steam has),
  4. the newest GE-Proton installed, if there is one (a community build with many game fixes),
  5. Proton 9 (an older one: some games broke with a newer version).
A fix is written where Steam keeps a game's own settings: the launch options (localconfig.vdf, the user's own words
and our per-game settings stay) or the "compatibility tool" (config.vdf, CompatToolMapping). Steam overwrites both on
exit, so Steam is closed first. The first fix keeps what was there before, and "Undo" puts it back exactly. A game
that then runs for a while (WORKED_S) keeps the fix that helped.
The words Proton and Wine are not shown to the user: the texts speak of the "Windows runtime".

A Linux version of a game (no compatdata folder: Steam never ran it through Proton) cannot be helped this way; the
summary says what can be done in Steam (verifying the game's files).
State: ~/.config/sloth-os/steam-doctor.json {appid: {failures: [{at, seconds}], step, original, status}}
"""
import json
import os
import re
import time
from pathlib import Path

from sloth_common import gamesettings
from sloth_common.apps import steam

STATE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "steam-doctor.json"
QUICK_S = 30       # closed sooner than this after starting: it did not start
WORKED_S = 120     # ran longer than this: the fix (if any) works
KEEP_FAILURES = 10

# The fixes in order: (key, kind, value); the key is also the text the user sees (sloth-center's texts.py)
STEPS = [
    ("nofsync", "env", ["PROTON_NO_FSYNC=1", "PROTON_NO_ESYNC=1"]),
    ("wined3d", "env", ["PROTON_USE_WINED3D=1"]),
    ("experimental", "tool", "proton_experimental"),
    ("ge", "tool", "GE-Proton"),          # the newest GE-Proton in compatibilitytools.d (skipped if none)
    ("older", "tool", "proton_9"),
]
OUR_ENV = {w.split("=")[0] for _k, kind, value in STEPS if kind == "env" for w in value}


def load(path=None):
    try:
        data = json.loads(Path(path or STATE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data, path=None):
    path = Path(path or STATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def record_run(appid, seconds, path=None, now=None):
    """The game-mode service saw a Steam game end after `seconds`. -> "failed", "worked" or "" (nothing to say)."""
    appid = str(appid)
    data = load(path)
    game = data.get(appid)
    if seconds < QUICK_S:
        game = data.setdefault(appid, {"failures": [], "step": -1, "original": None, "status": "failing"})
        game["failures"] = (game.get("failures", []) + [{"at": int(now or time.time()), "seconds": int(seconds)}])[
            -KEEP_FAILURES:]
        if game.get("status") == "works":
            game["status"] = "failing"
        save(data, path)
        return "failed"
    if game and seconds >= WORKED_S and game.get("status") != "works":
        game["status"] = "works"
        save(data, path)
        return "worked"
    return ""


def native(root, appid):
    """A Linux version of the game: Steam never ran it through Proton (no compatdata folder in any library)."""
    if not root:
        return False
    return not any((lib / "steamapps" / "compatdata" / str(appid)).is_dir() for lib in steam.library_folders(root))


def ge_proton(root):
    """The newest GE-Proton in Steam's compatibilitytools.d, or ""."""
    if not root:
        return ""
    names = [p.name for p in (Path(root) / "compatibilitytools.d").glob("GE-Proton*") if p.is_dir()]

    def key(name):
        return [int(n) for n in re.findall(r"\d+", name)]
    return max(names, key=key) if names else ""


def next_step(game, root):
    """The index of the next fix to try for this game, or None when every one was tried."""
    for i in range(game.get("step", -1) + 1, len(STEPS)):
        if STEPS[i][0] == "ge" and not ge_proton(root):
            continue
        return i
    return None


# --- Where Steam keeps a game's settings ---------------------------------------------------------------

def _node(data, keys):
    node = data
    for key in keys:
        child = steam.ci(node, key)
        if not isinstance(child, dict):
            child = node[key] = {}
        node = child
    return node


def _write_vdf(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".sloth-tmp")
    tmp.write_text(steam.vdf_dump(data) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_vdf(path):
    try:
        return steam.vdf_load(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def read_settings(root, localconfig, appid):
    """(launch options, compatibility tool entry or None) of a game."""
    apps = _node(_read_vdf(localconfig), ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"))
    options = steam.ci(steam.ci(apps, str(appid)) or {}, "LaunchOptions") or ""
    tools = _node(_read_vdf(Path(root) / "config" / "config.vdf"),
                  ("InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"))
    tool = tools.get(str(appid))
    return options, (dict(tool) if isinstance(tool, dict) else None)


def write_settings(root, localconfig, appid, options, tool):
    """Writes a game's launch options and compatibility tool (None: Steam's default). Steam must be closed."""
    data = _read_vdf(localconfig)
    apps = _node(data, ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"))
    entry = steam.ci(apps, str(appid))
    if not isinstance(entry, dict):
        entry = apps[str(appid)] = {}
    key = next((k for k in entry if k.lower() == "launchoptions"), "LaunchOptions")
    entry[key] = options
    _write_vdf(Path(localconfig), data)
    path = Path(root) / "config" / "config.vdf"
    data = _read_vdf(path)
    tools = _node(data, ("InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"))
    if tool:
        tools[str(appid)] = tool
    else:
        tools.pop(str(appid), None)
    _write_vdf(path, data)


def with_env(options, words, screen=(0, 0)):
    """The launch options with our fix's variables (an earlier fix's are taken out; the rest stays as it was)."""
    settings, rest, after = gamesettings.parse_launch_options(options)
    rest = [w for w in rest if w.split("=")[0] not in OUR_ENV]
    return gamesettings.build_launch_options(settings, list(words) + rest, after, screen or (0, 0))


def try_next(root, localconfig, appid, screen=(0, 0), path=None):
    """Applies the next fix (Steam must be closed). -> the fix's key, or None if every one was tried."""
    appid = str(appid)
    data = load(path)
    game = data.setdefault(appid, {"failures": [], "step": -1, "original": None, "status": "failing"})
    i = next_step(game, root)
    if i is None:
        game["status"] = "gave_up"
        save(data, path)
        return None
    options, tool = read_settings(root, localconfig, appid)
    if game.get("original") is None:
        game["original"] = {"options": options, "tool": tool}
    original = game["original"]
    key, kind, value = STEPS[i]
    # the current options (with the user's own changes since), only our fix's variables change
    if kind == "env":
        new_options, new_tool = with_env(options, value, screen), original["tool"]
    else:
        name = ge_proton(root) if key == "ge" else value
        new_options = with_env(options, [], screen) if options != original["options"] else options
        new_tool = {"name": name, "config": "", "priority": "250"}
    write_settings(root, localconfig, appid, new_options, new_tool)
    game.update(step=i, status="trying")
    save(data, path)
    return key


def undo(root, localconfig, appid, screen=(0, 0), path=None):
    """Takes our fix out (its variables from the launch options, the compatibility tool as it was before the first
    fix; the user's own changes since stay), and forgets the game. Steam must be closed."""
    appid = str(appid)
    data = load(path)
    game = data.pop(appid, None)
    if game and game.get("original") is not None:
        options, _tool = read_settings(root, localconfig, appid)
        original = game["original"]
        clean = options if options == original["options"] else with_env(options, [], screen)
        write_settings(root, localconfig, appid, clean, original["tool"])
    save(data, path)


def forget(appid, path=None):
    """The user does not want to hear about it (no fix applied): only the failures go."""
    data = load(path)
    game = data.get(str(appid))
    if game and game.get("step", -1) < 0:
        data.pop(str(appid))
        save(data, path)


def summary(appid, root=None, path=None):
    """What Sloth Center shows: {failures, lastSeconds, status, step (the key of the fix in use or ""), canTry,
    native}; None if nothing went wrong with this game."""
    game = load(path).get(str(appid))
    if not game:
        return None
    failures = game.get("failures", [])
    step = game.get("step", -1)
    return {"failures": len(failures), "lastSeconds": failures[-1]["seconds"] if failures else 0,
            "status": game.get("status", "failing"), "step": STEPS[step][0] if 0 <= step < len(STEPS) else "",
            "canTry": next_step(game, root) is not None, "native": native(root, appid),
            "changed": game.get("original") is not None}
