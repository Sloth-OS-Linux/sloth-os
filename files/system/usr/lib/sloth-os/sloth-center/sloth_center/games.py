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

from sloth_common import gamesettings
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


def place_label(path, root):
    """A library's name for the user: the main drive, or the drive's name."""
    path = Path(path)
    if steam_library._same(path, root):
        return tr("Main drive")
    return path.parent.name if path.name == steam_library.LIBRARY_NAME else path.name


class GamesController(QObject):
    changed = Signal()
    _moved = Signal(str, str, str)  # from the background thread: game id, error key ("" = done), new place

    def __init__(self, parent=None):
        super().__init__(parent)
        self._games = []
        self._error = ""
        self._info = ""
        self._steam_running = False
        self._moving = ""  # the id of the game being moved
        self._moved.connect(self._on_moved)
        self.refresh()

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
            games.append({"id": "steam:" + g["appid"], "name": g["name"], "source": "steam", **settings,
                          "place": place_label(found["library"], root) if found else "",
                          "size": texts.size_text(found["size"]) if found and found["size"] else "",
                          "movable": movable and found is not None})
        for app in library.all_apps():
            if app.kind != "windows" or app.id == library.SHARED_ID:
                continue
            games.append({"id": "win:" + app.id, "name": app.name, "source": "windows",
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
