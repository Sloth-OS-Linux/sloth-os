"""Játékok: játékonkénti beállítások (FPS-kijelző, teljesítmény mód, felskálázás).

A Steames játékok beállítása a Steam saját indítási beállításaiba kerül (localconfig.vdf, a
felhasználó saját beírásai megmaradnak); ezt csak akkor lehet írni, ha a Steam nem fut, különben
kilépéskor felülírja. A Windows-programoknál (sloth-exe) a program adatai közé kerül (sloth_common.apps), és a
.exe kezelő indításkor alkalmazza. Jelszó nem kell: minden a felhasználó saját mappájában van.
"""
import logging
import re
import subprocess

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from sloth_common import gamesettings
from sloth_common.apps import library, steam
from sloth_common.apps.steam import steam_root, vdf_dump, vdf_load

from .i18n import tr
log = logging.getLogger("sloth-center.games")

# Nem játékok: futtatókörnyezetek, Proton, közös összetevők
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
    """A legutóbb használt Steam-fiók beállításfájlja."""
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
    """A fő kijelző felbontása képpontban (a felskálázás célfelbontása)."""
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return (1920, 1080)
    size, ratio = screen.size(), screen.devicePixelRatio()
    return (int(size.width() * ratio), int(size.height() * ratio))


class GamesController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._games = []
        self._error = ""
        self._info = ""
        self._steam_running = False
        self.refresh()

    games = Property("QVariantList", lambda self: list(self._games), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    steamRunning = Property(bool, lambda self: self._steam_running, notify=changed)

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
        for g in steam_games():
            options = _ci(_ci(apps, g["appid"]) or {}, "LaunchOptions") or ""
            settings, _rest, _after = gamesettings.parse_launch_options(options)
            games.append({"id": "steam:" + g["appid"], "name": g["name"], "source": "steam", **settings})
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
        source, key = game_id.split(":", 1)
        if source == "steam":
            self._save_steam(key, settings)
        else:
            self._save_windows(key, settings)
        self.refresh()

    def _save_steam(self, appid, settings):
        if steam_running():
            self._error = tr("Zárd be a Steamet, és utána állítsd át: a Steam futás közben felülírná.")
            return
        cfg = localconfig_path()
        if not cfg:
            self._error = tr("A Steam beállításai nem találhatók. Indítsd el egyszer a Steamet, és jelentkezz be.")
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
            self._info = tr("Elmentve. A következő indításkor lép életbe.")
        except OSError as e:
            log.warning("localconfig.vdf: %s", e)
            self._error = tr("Nem sikerült menteni.")

    def _save_windows(self, app_id, settings):
        app = library.find(app_id)
        try:
            if app is None:
                raise OSError(f"nincs ilyen program: {app_id}")
            app.save_meta(game=settings)
            self._info = tr("Elmentve. A következő indításkor lép életbe.")
        except OSError as e:
            log.warning("program adatai: %s", e)
            self._error = tr("Nem sikerült menteni.")

    @Slot()
    def closeSteam(self):
        """A Steam rendes leállítása (mint a Kilépés menüpont)."""
        for cmd in (["flatpak", "run", "com.valvesoftware.Steam", "-shutdown"], ["steam", "-shutdown"]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                continue
