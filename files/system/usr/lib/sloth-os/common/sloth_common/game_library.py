"""One library for every game (Sloth Center → Games): the games of Steam, Heroic (Epic, GOG, Amazon), the Flatpak
games and the Windows games, each with a cover and a way to start it.

Covers:
  - Steam keeps them in its library cache: once <appid>_library_600x900.jpg, since 2026 a folder per game with hashed
    names (librarycache/<appid>/[<hash>/]…); we look for "library_600x900" first, then any portrait image there.
    Without one: Steam's image server (two addresses: newer games may be missing from the first), into our cache.
  - Epic (Heroic): the tall box art's address from legendary's metadata (keyImages: DieselGameBoxTall), into our
    cache. GOG and Amazon: their icon only (the files of those stores were not looked at in detail).
  - A recognized Windows game: its umu id is often a Steam id (umu-<number>): then Steam's cover.
  - Flatpak games: their app icon.
Starting: Steam steam://rungameid/<id>, Heroic heroic://launch?appName=…&runner=… (Heroic's own protocol: src/backend
/protocol.ts), Flatpak `flatpak run <id>`; Windows games through Sloth Center's Windows programs (the .exe handler).

TV mode shows the games that are not Steam's in Steam's own list (other_games, tv_launch; /usr/libexec/sloth-os/
tv-shortcuts and tv-launch): there Heroic starts without its window (--no-gui, as Heroic's own "Add to Steam" does).
"""
import json
import os
import re
import struct
import urllib.parse
from pathlib import Path

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "covers"
STEAM_CDN = ("https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{id}/library_600x900.jpg",
             "https://cdn.cloudflare.steamstatic.com/steam/apps/{id}/library_600x900.jpg")
HEROIC_ROOTS = (".var/app/com.heroicgameslauncher.hgl/config/heroic", ".config/heroic")
HEROIC_FLATPAK = "com.heroicgameslauncher.hgl"
# where the Flatpak apps' icons are (the system's and the user's installation)
FLATPAK_ICONS = (Path("/var/lib/flatpak/exports/share/icons/hicolor"),
                 Path.home() / ".local/share/flatpak/exports/share/icons/hicolor")
# Flatpak apps in the "Game" category that are launchers or tools, not games
NOT_GAMES = {"com.valvesoftware.Steam", "com.heroicgameslauncher.hgl", "net.lutris.Lutris", "com.usebottles.bottles",
             "net.davidotek.pupgui2", "com.vysp3r.ProtonPlus", "io.github.philipk.boilr", "com.github.Matoking.protontricks",
             "io.github.ilya_zlobintsev.LACT", "com.steamgriddb.steam-rom-manager", "com.github.mtkennerly.ludusavi",
             "io.github.benjamimgois.goverlay"}


def image_size(path):
    """(width, height) of a JPEG or PNG from its header, or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:2] != b"\xff\xd8":
                return None
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                if marker[1] in (0xD8, 0x01) or 0xD0 <= marker[1] <= 0xD7:
                    continue
                length = struct.unpack(">H", f.read(2))[0]
                if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", f.read(5)[1:5])
                    return (w, h)
                f.seek(length - 2, 1)
    except (OSError, struct.error):
        return None


def _portrait(path):
    size = image_size(path)
    return bool(size) and size[1] > size[0] * 1.3


def steam_cover(root, appid):
    """The local cover of a Steam game, or ""."""
    cache = Path(root) / "appcache" / "librarycache"
    flat = sorted(cache.glob(f"{appid}_library_600x900*.jpg"))
    if flat:
        return str(flat[-1])
    folder = cache / str(appid)
    if not folder.is_dir():
        return ""
    images = [p for p in list(folder.glob("*")) + list(folder.glob("*/*"))
              if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    named = sorted((p for p in images if p.name.startswith("library_600x900")), key=lambda p: p.name)
    if named:
        return str(named[-1])
    portraits = [p for p in images if _portrait(p)]
    return str(max(portraits, key=lambda p: p.stat().st_size)) if portraits else ""


def cached_cover(key):
    """The cover we downloaded before for this game id, or ""."""
    path = CACHE / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".jpg")
    return str(path) if path.is_file() and path.stat().st_size > 0 else ""


def cache_path(key):
    return CACHE / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".jpg")


def steam_entry(root, appid, name):
    cover = steam_cover(root, appid) if root else ""
    return {"id": f"steam:{appid}", "name": name, "source": "steam",
            "cover": cover or cached_cover(f"steam:{appid}"),
            "remote": [] if cover else [u.format(id=appid) for u in STEAM_CDN],
            "launch": ["xdg-open", f"steam://rungameid/{appid}"]}


def _json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def heroic_root(home=None):
    home = Path(home or Path.home())
    return next((home / r for r in HEROIC_ROOTS if (home / r).is_dir()), None)


def _heroic_launch(app, runner):
    query = urllib.parse.urlencode({"appName": app, "runner": runner})
    return ["xdg-open", f"heroic://launch?{query}"]


def heroic_games(home=None):
    """The games Heroic installed: Epic (legendary), GOG, Amazon (nile)."""
    root = heroic_root(home)
    if not root:
        return []
    games = []
    # Epic: installed.json is {app_name: {install_path, …}}, the title and the art in metadata/<app_name>.json
    epic = root / "legendaryConfig" / "legendary"
    for app, info in (_json(epic / "installed.json") or {}).items():
        meta = (_json(epic / "metadata" / f"{app}.json") or {}).get("metadata") or {}
        title = meta.get("title") or (info or {}).get("title") or app
        tall = [i.get("url") for i in meta.get("keyImages") or []
                if i.get("type") in ("DieselGameBoxTall", "OfferImageTall") and i.get("url")]
        games.append({"id": f"epic:{app}", "name": title, "source": "epic", "cover": cached_cover(f"epic:{app}"),
                      "remote": tall[:1], "launch": _heroic_launch(app, "legendary"),
                      "folder": (info or {}).get("install_path") or ""})
    # GOG and Amazon: the list of installed games; the name from the install folder when nothing better is there
    for source, runner, path in (("gog", "gog", root / "gog_store" / "installed.json"),
                                 ("amazon", "nile", root / "nile_config" / "nile" / "installed.json")):
        data = _json(path)
        items = data.get("installed", []) if isinstance(data, dict) else data if isinstance(data, list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            app = str(item.get("appName") or item.get("id") or item.get("app_name") or "")
            folder = item.get("install_path") or item.get("path") or ""
            if not app:
                continue
            title = item.get("title") or (Path(folder).name if folder else "") or app
            games.append({"id": f"{source}:{app}", "name": title, "source": source, "cover": "",
                          "remote": [], "launch": _heroic_launch(app, runner), "folder": folder})
    return games


def flatpak_games():
    """Installed Flatpak apps in the "Game" category (not the launchers): [{id, name, icon, …}]."""
    try:
        from gi.repository import Gio
    except ImportError:
        return []
    out = []
    for info in Gio.AppInfo.get_all():
        app_id = (info.get_id() or "").removesuffix(".desktop")
        if not isinstance(info, Gio.DesktopAppInfo) or app_id in NOT_GAMES or not info.should_show():
            continue
        if "Game" not in (info.get_categories() or "").split(";"):
            continue
        if not info.get_string("X-Flatpak"):
            continue
        icon = info.get_icon()
        out.append({"id": f"flatpak:{app_id}", "name": info.get_name() or app_id, "source": "flatpak",
                    "cover": "", "icon": icon.to_string() if icon else "", "remote": [],
                    "launch": ["flatpak", "run", info.get_string("X-Flatpak")]})
    return out


def windows_games():
    """The Windows games of Sloth Center's Windows programs (recognized, a game launcher, or the user said so), with the
    command that starts them, as Windows programs → Start does. [{id, name, source, cover, icon, launch}]"""
    try:
        from .apps import imports, library, menu, packages
    except ImportError:
        return []
    out = []
    for app in library.all_apps():
        if not library.is_game(app):
            continue
        entries = menu.entries(app)
        launch = None
        how = {"link": imports.launch_command, "box": packages.box_launch_command,
               "appimage": lambda a: ["sloth-exe", "--run", a.id]}.get(app.kind)
        if how:
            launch = how(app)
        else:
            target = next((e["target"] for e in entries if e["target"]), None)
            launch = ["sloth-exe", "--launch", app.id, target] if target else None
        if not launch:
            continue
        icon = next((e["icon"] for e in entries if e["icon"].startswith("/")), "")
        out.append({"id": "win:" + app.id, "name": app.name, "source": "windows",
                    "cover": cached_cover("win:" + app.id), "icon": icon, "launch": launch, "folder": ""})
    return out


def flatpak_icon(app_id):
    """The Flatpak app's icon file (the biggest PNG; Steam takes no SVG), or ""."""
    for base in FLATPAK_ICONS:
        for size in ("512x512", "256x256", "128x128", "64x64"):
            path = base / size / "apps" / f"{app_id}.png"
            if path.is_file():
                return str(path)
    return ""


def other_games():
    """The games that are not Steam's, for TV mode: Heroic's, the Flatpak games, the Windows games.
    [{id, name, source, cover (a file or ""), icon (a file or ""), launch, folder}] (folder: where the game is
    installed, for the stores whose start command returns at once)."""
    games = []
    for part in (heroic_games, flatpak_games, windows_games):
        try:
            games += part()
        except Exception:  # noqa: BLE001 - a broken file of one launcher must not hide the others' games
            continue
    for g in games:
        if g["source"] == "flatpak":
            g["icon"] = flatpak_icon(g["id"].partition(":")[2])
        elif not str(g.get("icon", "")).startswith("/"):
            g["icon"] = ""
        g.setdefault("folder", "")
    return games


def tv_launch(game):
    """The command TV mode starts a game with: Heroic's games without Heroic's window (Heroic's own "Add to Steam" way),
    the rest as Sloth Center starts them."""
    if game["source"] in ("epic", "gog", "amazon"):
        url = game["launch"][-1]
        heroic = (["flatpak", "run", HEROIC_FLATPAK] if (Path.home() / HEROIC_ROOTS[0]).is_dir() else ["heroic"])
        return heroic + ["--no-gui", "--no-sandbox", url]
    return list(game["launch"])


def windows_cover(gameid):
    """A recognized Windows game: its umu id is often the Steam id ("umu-1145360") -> Steam's cover addresses."""
    m = re.fullmatch(r"umu-(\d+)", gameid or "")
    return [u.format(id=m[1]) for u in STEAM_CDN] if m else []


def download(key, urls, timeout=6):
    """The first address that gives an image goes into our cache. -> its path, or ""."""
    import urllib.request
    path = cache_path(key)
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Sloth-OS"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status != 200 or not (r.headers.get("Content-Type") or "").startswith("image/"):
                    continue
                data = r.read(8 * 1024 * 1024)
        except OSError:
            continue
        if len(data) < 1000:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        return str(path)
    return ""
