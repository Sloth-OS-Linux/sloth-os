"""Játékok: játékonkénti beállítások (FPS-kijelző, teljesítmény mód, felskálázás).

A Steames játékok beállítása a Steam saját indítási beállításaiba kerül (localconfig.vdf, a
felhasználó saját beírásai megmaradnak); ezt csak akkor lehet írni, ha a Steam nem fut, különben
kilépéskor felülírja. A Windows-programoknál (sloth-exe) a program meta.json-jába kerül, és a
.exe kezelő indításkor alkalmazza. Jelszó nem kell: minden a felhasználó saját mappájában van.
"""
import json
import logging
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from sloth_common import gamesettings

from .i18n import tr
from .winprograms import ROOT as WIN_ROOT

log = logging.getLogger("sloth-center.games")

STEAM_ROOTS = [Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
               Path.home() / ".local/share/Steam", Path.home() / ".steam/steam"]
# Nem játékok: futtatókörnyezetek, Proton, közös összetevők
NOT_GAMES = re.compile(r"proton|steam linux runtime|steamworks common|steamvr|redistributable|soundtrack", re.I)


# --- A Steam szöveges VDF formátuma ----------------------------------------------------------

_TOKEN = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|(//[^\n]*)')


def vdf_load(text):
    stack, key = [{}], None
    for m in _TOKEN.finditer(text):
        s, brace, comment = m.groups()
        if comment:
            continue
        if brace == "{":
            node = {}
            stack[-1][key] = node
            stack.append(node)
            key = None
        elif brace == "}":
            stack.pop()
        elif key is None:
            key = s.replace('\\"', '"').replace("\\\\", "\\")
        else:
            stack[-1][key] = s.replace('\\"', '"').replace("\\\\", "\\")
            key = None
    return stack[0]


def vdf_dump(data, indent=0):
    out = []
    for k, v in data.items():
        q = lambda x: '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, dict):
            out.append("\t" * indent + q(k))
            out.append("\t" * indent + "{")
            out.append(vdf_dump(v, indent + 1))
            out.append("\t" * indent + "}")
        else:
            out.append("\t" * indent + q(k) + "\t\t" + q(v))
    return "\n".join(x for x in out if x)


def _ci(d, key):
    """A Steam fájljaiban a kulcsok kis- és nagybetűje változhat."""
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return None


# --- Steam -----------------------------------------------------------------------------------

def steam_root():
    return next((r for r in STEAM_ROOTS if (r / "steamapps").is_dir()), None)


def steam_games():
    root = steam_root()
    if not root:
        return []
    libraries = {root}
    try:
        folders = _ci(vdf_load((root / "steamapps/libraryfolders.vdf").read_text(errors="replace")),
                      "libraryfolders") or {}
        libraries |= {Path(_ci(v, "path")) for v in folders.values() if isinstance(v, dict) and _ci(v, "path")}
    except OSError:
        pass
    games = {}
    for lib in libraries:
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
        for meta_path in sorted(WIN_ROOT.glob("*/meta.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            games.append({"id": "win:" + meta_path.parent.name, "name": meta.get("name", meta_path.parent.name),
                          "source": "windows", **gamesettings.normalize(meta.get("game"))})
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

    def _save_windows(self, slug, settings):
        meta_path = WIN_ROOT / slug / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["game"] = settings
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            self._info = tr("Elmentve. A következő indításkor lép életbe.")
        except (OSError, ValueError) as e:
            log.warning("meta.json: %s", e)
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
