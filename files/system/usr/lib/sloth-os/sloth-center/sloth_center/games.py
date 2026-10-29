"""Games: per-game settings (FPS display, performance mode, upscaling), and moving a Steam game to another drive.

For Steam games the setting goes into Steam's own launch options (localconfig.vdf, the
user's own entries stay); this can only be written while Steam is not running, otherwise
it overwrites it on exit. For Windows programs (sloth-exe) it goes into the program's data (sloth_common.apps), and the
.exe handler applies it when starting. No password is needed: everything is in the user's own folder.
Moving a Steam game is sloth_common.apps.steam_library (in the background: copying a big game takes a while).
"""
import logging
import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from sloth_common import game_check, gamesettings
from sloth_common.apps import library, steam, steam_library
from sloth_common.apps.steam import steam_root, vdf_dump, vdf_load

from . import texts
from .i18n import N_, tr
log = logging.getLogger("sloth-center.games")

# Not games: runtimes, Proton, shared components
NOT_GAMES = re.compile(r"proton|steam linux runtime|steamworks common|steamvr|redistributable|soundtrack", re.I)
_ci = steam.ci


def steam_games():
    root = steam_root()
    if not root:
        return []
    games = {}
    for lib in steam.library_folders(root):
        for manifest in (lib / "steamapps").glob("appmanifest_*.acf"):
            try:
                state = _ci(vdf_load(manifest.read_text(errors="replace")), "AppState") or {}
            except OSError:
                continue
            appid, name = _ci(state, "appid"), _ci(state, "name") or ""
            if appid and name and not NOT_GAMES.search(name):
                games[appid] = name
    return sorted(({"appid": a, "name": n} for a, n in games.items()), key=lambda g: g["name"].lower())


def localconfig_path():
    """The settings file of the Steam account used last."""
    root = steam_root()
    if not root:
        return None
    configs = sorted((root / "userdata").glob("*/config/localconfig.vdf"), key=lambda p: p.stat().st_mtime)
    return configs[-1] if configs else None


def _apps_node(data):
    node = data
    for key in ("UserLocalConfigStore", "Software", "Valve", "Steam"):
        child = _ci(node, key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    apps = _ci(node, "apps")
    if not isinstance(apps, dict):
        apps = {}
        node["apps"] = apps
    return apps


def steam_running():
    return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0


def screen_size():
    """The main display's resolution in pixels (the target resolution of upscaling)."""
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return (1920, 1080)
    size, ratio = screen.size(), screen.devicePixelRatio()
    return (int(size.width() * ratio), int(size.height() * ratio))


# What went wrong while moving a game (steam_library.move_game) -> the text the user sees
MOVE_ERRORS = {
    "not_found": N_("The game wasn't found. Refresh the list and try again."),
    "same_place": N_("The game is already there."),
    "unsupported": N_("Games can't go on that drive: its file system doesn't support them."),
    "exists": N_("There is already a copy of this game on that drive. Remove it in Steam first."),
    "no_space": N_("There isn't enough free space on that drive."),
    "no_access": N_("Steam couldn't be given access to that drive."),
    "copy_failed": N_("Moving didn't work. The game stayed where it was and still works."),
}


# The "Will it run?" verdicts (sloth_common.game_check): (mark, text)
BADGES = {
    "great": ("🟢", N_("Runs well")),
    "ok": ("🟡", N_("Runs, but may have issues")),
    "poor": ("🟠", N_("Often doesn't start")),
    "blocked": ("🔴", N_("Blocked by its makers")),
    "broken": ("🔴", N_("Its anti-cheat blocks it")),
    "tested": ("🦥", N_("Tested by Sloth OS")),
    "unknown": ("⚪", N_("Too few reports")),
}
TESTED = {
    "works": N_("The Sloth OS team tried it: it works."),
    "issues": N_("The Sloth OS team tried it: it works, with some issues."),
    "no": N_("The Sloth OS team tried it: it didn't work."),
}


def describe(v):
    """A verdict (game_check.verdict) as the page shows it: the mark, the badge text and the explanation lines."""
    mark, badge = BADGES.get(v["badge"], BADGES["unknown"])
    badge_text, lines = "", []
    if v["badge"] == "alternative":
        # its Windows version is blocked, but a community app runs it: that is the answer, not the block
        mark, badge = "🟢", ""
        badge_text = tr("Runs with {app}", app=v["alternative"])
        lines.append(tr("Its Windows version is blocked on Linux, but {app}, a community app made for Linux, runs it. "
                        "Sloth Welcome and Discover can install it.", app=v["alternative"]))
    if v["badge"] == "blocked" and v["publisher"]:
        lines.append(tr("Not Sloth OS's fault: {publisher} doesn't allow the game on Linux. If you'd like to play it "
                        "here, tell {publisher}. 🦥", publisher=v["publisher"]))
    elif v["badge"] == "blocked":
        lines.append(tr("Not Sloth OS's fault: the game's makers don't allow it on Linux. If you'd like to play it "
                        "here, tell them. 🦥"))
    elif v["badge"] == "broken":
        lines.append(tr("Its anti-cheat doesn't work on Linux, so it can't be played (or only offline)."))
    if v["tested"]:
        lines.append(tr(TESTED.get(v["tested"], TESTED["works"])))
    if v["works"] >= 0 and v["reports"]:
        lines.append(tr("{works}% of {reports} players say it works.", works=v["works"], reports=v["reports"]))
    if v["gpus"]:
        lines.append(tr("By graphics card: {list}", list=" · ".join(f"{n} {p}%" for n, p in v["gpus"])))
    if v["anticheat"]:
        lines.append(tr("Anti-cheat: {names}", names=", ".join(v["anticheat"])))
    if v["native"]:
        lines.append(tr("It has its own Linux version."))
    if v["known"]:
        lines.append(tr("A setting that worked for other players is known: Sloth OS uses it by itself."))
    if v["sources"]:
        lines.append(tr("Source: {sources}", sources=", ".join(v["sources"])))
    return {"name": v["name"], "badge": v["badge"], "mark": mark, "badgeText": tr(badge) if badge else badge_text,
            "lines": lines}


def place_label(path, root):
    """A library's name for the user: the main drive, or the drive's name."""
    path = Path(path)
    if steam_library._same(path, root):
        return tr("Main drive")
    return path.parent.name if path.name == steam_library.LIBRARY_NAME else path.name


class GamesController(QObject):
    changed = Signal()
    _moved = Signal(str, str, str)  # from the background thread: game id, error key ("" = done), new place
    _indexed = Signal(bool)  # from the background thread: the "Will it run?" list was downloaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self._games = []
        self._error = ""
        self._info = ""
        self._steam_running = False
        self._moving = ""  # the id of the game being moved
        self._moved.connect(self._on_moved)
        # "Will it run?": the game list (kept on disk, downloaded weekly in the background)
        self._index, self._names, self._known = {}, {}, set()
        self._index_state = "loading"
        self._indexed.connect(self._on_indexed)
        self._load_index()
        if game_check.needs_download():
            threading.Thread(target=lambda: self._indexed.emit(game_check.download()), daemon=True).start()
        else:
            self._index_state = "ready" if self._index else "missing"
        self.refresh()

    def _load_index(self):
        self._index = game_check.load()
        self._names = game_check.index_names(self._index)
        self._known = game_check.known_settings()

    def _on_indexed(self, downloaded):
        if downloaded:
            self._load_index()
        self._index_state = "ready" if self._index else "missing"
        self.refresh()

    # "ready", "loading" (the first download is running) or "missing" (not downloaded yet: no internet)
    checkState = Property(str, lambda self: self._index_state, notify=changed)

    @Slot(str, result="QVariantList")
    def checkSearch(self, query):
        """"Will it run?": the games whose name matches, with the verdict and its explanation."""
        return [describe(v) for v in game_check.search(self._index, query, self._known, names=self._names)]

    games = Property("QVariantList", lambda self: list(self._games), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    steamRunning = Property(bool, lambda self: self._steam_running, notify=changed)
    movingId = Property(str, lambda self: self._moving, notify=changed)

    @Slot()
    def refresh(self):
        self._steam_running = steam_running()
        games = []
        cfg = localconfig_path()
        apps = {}
        if cfg:
            try:
                apps = _apps_node(vdf_load(cfg.read_text(errors="replace")))
            except OSError:
                pass
        root = steam_root()
        movable = root is not None and len(steam_library.targets(root)) > 1
        for g in steam_games():
            options = _ci(_ci(apps, g["appid"]) or {}, "LaunchOptions") or ""
            settings, _rest, _after = gamesettings.parse_launch_options(options)
            found = steam_library.find_game(root, g["appid"]) if root else None
            check = game_check.lookup(self._index, g["appid"], self._known)
            games.append({"id": "steam:" + g["appid"], "name": g["name"], "source": "steam", **settings,
                          "check": describe(check) if check else {},
                          "place": place_label(found["library"], root) if found else "",
                          "size": texts.size_text(found["size"]) if found and found["size"] else "",
                          "movable": movable and found is not None})
        for app in library.all_apps():
            if app.kind != "windows" or app.id == library.SHARED_ID:
                continue
            games.append({"id": "win:" + app.id, "name": app.name, "source": "windows", "check": {},
                          **gamesettings.normalize(app.meta.get("game"))})
        self._games = sorted(games, key=lambda g: g["name"].lower())
        self.changed.emit()

    @Slot(str, str, "QVariant")
    def setOption(self, game_id, option, value):
        self._error, self._info = "", ""
        game = next((g for g in self._games if g["id"] == game_id), None)
        if not game or option not in gamesettings.DEFAULTS:
            return
        settings = gamesettings.normalize({**{k: game[k] for k in gamesettings.DEFAULTS}, option: value})
        if option == "fps" and value:
            # the temperatures and the memory too (only where the user has no MangoHud settings of their own)
            gamesettings.ensure_overlay_config()
        source, key = game_id.split(":", 1)
        if source == "steam":
            self._save_steam(key, settings)
        else:
            self._save_windows(key, settings)
        self.refresh()

    def _save_steam(self, appid, settings):
        if steam_running():
            self._error = tr("Close Steam first, then change this: Steam would overwrite it while running.")
            return
        cfg = localconfig_path()
        if not cfg:
            self._error = tr("Steam's settings were not found. Start Steam once and sign in.")
            return
        try:
            data = vdf_load(cfg.read_text(errors="replace"))
            apps = _apps_node(data)
            app = _ci(apps, appid)
            if not isinstance(app, dict):
                app = {}
                apps[appid] = app
            current = _ci(app, "LaunchOptions") or ""
            _old, rest, after = gamesettings.parse_launch_options(current)
            new = gamesettings.build_launch_options(settings, rest, after, screen_size())
            for k in [k for k in app if k.lower() == "launchoptions"]:
                del app[k]
            app["LaunchOptions"] = new
            backup = cfg.with_suffix(".vdf.sloth-backup")
            if not backup.exists():
                backup.write_bytes(cfg.read_bytes())
            tmp = cfg.with_suffix(".tmp")
            tmp.write_text(vdf_dump(data) + "\n", encoding="utf-8")
            tmp.replace(cfg)
            self._info = tr("Saved. It takes effect the next time you start it.")
        except OSError as e:
            log.warning("localconfig.vdf: %s", e)
            self._error = tr("Could not save.")

    def _save_windows(self, app_id, settings):
        app = library.find(app_id)
        try:
            if app is None:
                raise OSError(f"no such program: {app_id}")
            app.save_meta(game=settings)
            self._info = tr("Saved. It takes effect the next time you start it.")
        except OSError as e:
            log.warning("program adatai: %s", e)
            self._error = tr("Could not save.")

    # --- Moving a Steam game to another drive ---

    @Slot(str, result="QVariantList")
    def moveTargets(self, game_id):
        """The drives the game can go to (not where it is now): [{"path", "label", "free"}]."""
        root = steam_root()
        found = steam_library.find_game(root, game_id.split(":", 1)[1]) if root and game_id.startswith("steam:") else None
        if not found:
            return []
        return [{"path": t["path"], "label": place_label(t["path"], root),
                 "free": tr("{size} free", size=texts.size_text(t["free"]))}
                for t in steam_library.targets(root) if not steam_library._same(t["path"], found["library"])]

    @Slot(str, str)
    def moveGame(self, game_id, target):
        """Moves the game in the background; the page shows the progress, and the result when it is done."""
        self._error, self._info = "", ""
        root = steam_root()
        if self._moving or not root or not game_id.startswith("steam:"):
            return
        if steam_running():
            self._error = tr("Close Steam first, then move the game: Steam would undo it while running.")
            self.changed.emit()
            return
        self._moving = game_id
        self.changed.emit()
        appid = game_id.split(":", 1)[1]

        def work():
            try:
                result = steam_library.move_game(root, appid, target, flatpak=steam.is_flatpak(root))
            except OSError as e:
                log.warning("moving %s: %s", appid, e)
                result = "copy_failed"
            self._moved.emit(game_id, result, place_label(target, root))
        threading.Thread(target=work, daemon=True).start()

    def _on_moved(self, game_id, result, place):
        name = next((g["name"] for g in self._games if g["id"] == game_id), "")
        self._moving = ""
        if result:
            self._error = tr(MOVE_ERRORS.get(result, MOVE_ERRORS["copy_failed"]))
        else:
            self._info = tr("{name} is now on {place}. Start Steam and play as before.", name=name, place=place)
        self.refresh()

    @Slot()
    def closeSteam(self):
        """Stops Steam properly (like the Exit menu item)."""
        for cmd in (["flatpak", "run", "com.valvesoftware.Steam", "-shutdown"], ["steam", "-shutdown"]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
