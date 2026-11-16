"""Game mode: while a game runs, the computer is set up for it by itself (/usr/libexec/sloth-os/game-mode).

What counts as a game (looked at every few seconds in /proc, only the user's own processes):
  - a Steam game: Steam starts every game through its "reaper" with "SteamLaunch AppId=<number>" on the command line
    (native and Windows games alike; the Flatpak Steam's processes are visible from outside too);
  - a recognized Windows game: umu runs it with GAMEID=<id> in its environment (the .exe handler sets it for the
    programs it recognized, Heroic and Lutris do the same); "umu-default" (a program nothing is known about) and
    "0" are not counted, so an ordinary Windows program does not start game mode;
  - anything GameMode already serves (a game with the per-game "performance mode" on, started with gamemoderun) is
    seen through GameMode's ClientCount by the service itself.

While one runs: notifications wait (Do Not Disturb), GameMode serves the game even without the per-game setting, the
power mode is "best performance" when plugged in, and background work waits (updates, the game save backup, the
download of the Windows runtime): their units ask `game-mode playing` first (ExecCondition). Afterwards everything
goes back, and the user's skipped jobs run.

The setting (on by default): ~/.config/sloth-os/game-mode.json {"enabled": true}. While a game runs the service
writes $XDG_RUNTIME_DIR/sloth-os/gaming ({"name", "since"}); Sloth Center shows it.
"""
import json
import os
import re
import time
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "game-mode.json"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "sloth-os"
STATE = RUNTIME / "gaming"
SKIPPED = RUNTIME / "game-mode-skipped"
DEFAULTS = {"enabled": True}
NOT_A_GAME_ID = {"", "0", "umu-0", "umu-default", "none"}
STEAM_ROOTS = (".var/app/com.valvesoftware.Steam/.local/share/Steam", ".var/app/com.valvesoftware.Steam/data/Steam",
               ".local/share/Steam", ".steam/steam")


def load(path=None):
    try:
        data = json.loads(Path(path or CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"enabled": bool(data.get("enabled", DEFAULTS["enabled"]))}


def save(enabled, path=None):
    path = Path(path or CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"enabled": bool(enabled)}) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read(path):
    try:
        return Path(path).read_bytes()
    except OSError:
        return b""


def game_of(cmdline, environ):
    """One process -> (kind, id) if it is a game, else None. cmdline and environ as lists of strings."""
    if "SteamLaunch" in cmdline:
        for arg in cmdline:
            m = re.fullmatch(r"AppId=(\d+)", arg)
            if m and m[1] != "0":
                return ("steam", m[1])
    for item in environ:
        if item.startswith("GAMEID="):
            gid = item.split("=", 1)[1].strip()
            if gid.lower() not in NOT_A_GAME_ID:
                return ("umu", gid)
    return None


def program_name(cmdline):
    """A readable name from a Windows program's command line: "Witcher3" from …\\bin\\x64\\witcher3.exe."""
    for arg in reversed(cmdline):
        if arg.lower().endswith(".exe"):
            return re.split(r"[\\/]", arg)[-1][:-4]
    return ""


def steam_name(appid, home=None):
    """A Steam game's name from its appmanifest in any of Steam's libraries, or ""."""
    home = Path(home or Path.home())
    libraries = []
    for root in STEAM_ROOTS:
        root = home / root
        if not (root / "steamapps").is_dir():
            continue
        libraries.append(root / "steamapps")
        vdf = _read(root / "steamapps" / "libraryfolders.vdf").decode("utf-8", "replace")
        libraries += [Path(p.replace("\\\\", "\\")) / "steamapps" for p in re.findall(r'"path"\s+"([^"]+)"', vdf)]
    for lib in libraries:
        text = _read(lib / f"appmanifest_{appid}.acf").decode("utf-8", "replace")
        m = re.search(r'"name"\s+"([^"]+)"', text)
        if m:
            return m[1]
    return ""


def find_games(proc="/proc", uid=None, home=None):
    """The games running now: {(kind, id): {"pids": [...], "name": str}}, only the user's own processes."""
    uid = os.getuid() if uid is None else uid
    games = {}
    for entry in os.scandir(proc):
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
        except OSError:
            continue
        cmdline = [a for a in _read(f"{entry.path}/cmdline").decode("utf-8", "replace").split("\0") if a]
        if not cmdline:
            continue
        environ = _read(f"{entry.path}/environ").decode("utf-8", "replace").split("\0")
        key = game_of(cmdline, environ)
        if not key:
            continue
        game = games.setdefault(key, {"pids": [], "name": ""})
        game["pids"].append(int(entry.name))
        if not game["name"]:
            game["name"] = steam_name(key[1], home) if key[0] == "steam" else program_name(cmdline)
    for key, game in games.items():
        game["pids"].sort()
        game["name"] = game["name"] or (f"Steam {key[1]}" if key[0] == "steam" else key[1])
    return games


def write_state(names, path=None, now=None):
    path = Path(path or STATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": ", ".join(names), "since": int(now or time.time())}) + "\n", encoding="utf-8")


def read_state(path=None):
    """{"name", "since"} while a game runs, else None."""
    try:
        return json.loads(Path(path or STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clear_state(path=None):
    try:
        Path(path or STATE).unlink()
    except OSError:
        pass


def anyone_playing(run_user="/run/user"):
    """For units of the system (updates): does any signed-in user play now?"""
    try:
        return any((Path(run_user) / d / "sloth-os" / "gaming").exists() for d in os.listdir(run_user))
    except OSError:
        return False


def on_mains(power_supply="/sys/class/power_supply"):
    """True if plugged in, or a computer without a battery."""
    batteries = mains = 0
    online = False
    try:
        for d in Path(power_supply).iterdir():
            kind = _read(d / "type").decode().strip()
            if kind == "Battery" and _read(d / "scope").decode().strip() != "Device":
                batteries += 1
            elif kind == "Mains":
                mains += 1
                online = online or _read(d / "online").decode().strip() == "1"
    except OSError:
        return True
    return online or batteries == 0
