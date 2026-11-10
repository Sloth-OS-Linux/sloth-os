"""Moving over from Windows: bringing over the user folders (Desktop, Documents…) and the browser bookmarks.

The Windows partition is only mounted read-only (udisksctl, with the system's password prompt if needed), and nothing
is written to it. The files go into the matching Sloth OS folders (xdg-user-dir); whatever is already there with the
same size is skipped (so an interrupted copy can continue), and a different file with the same name gets a "(Windows)" suffix.
The bookmarks (Chrome, Edge, Firefox) go into an HTML file on the Desktop; any browser can import it.
The OneDrive folder is skipped: it can be reached through the Cloud storage card in Sloth Center.
The programs in Windows' Start menu are matched to the wizard's apps (programs()), and the installed Steam games are
copied into Sloth OS's Steam library, so they need no new download (steam_games(), copy_games()).

Sloth Welcome (sloth_welcome) uses it; Sloth Center (Disks) opens Welcome with this step.
"""
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

from .apps import steam

# The Windows folder's name -> the xdg-user-dir key
FOLDERS = {
    "desktop": ("Desktop", "DESKTOP"),
    "documents": ("Documents", "DOCUMENTS"),
    "downloads": ("Downloads", "DOWNLOAD"),
    "music": ("Music", "MUSIC"),
    "pictures": ("Pictures", "PICTURES"),
    "videos": ("Videos", "VIDEOS"),
}
SKIP_USERS = {"public", "default", "default user", "all users", "defaultapppool", "wdagutilityaccount"}
SKIP_FILES = {"desktop.ini", "thumbs.db"}
SKIP_SUFFIXES = (".lnk",)       # Windows shortcuts: they do not work on Linux
MIN_NTFS_BYTES = 10 * 1024**3   # a smaller NTFS partition (e.g. recovery) is not a Windows system
CHROMIUM_BROWSERS = {
    "Google Chrome": "AppData/Local/Google/Chrome/User Data",
    "Microsoft Edge": "AppData/Local/Microsoft/Edge/User Data",
}
FIREFOX_PROFILES = "AppData/Roaming/Mozilla/Firefox/Profiles"


# --- Partitions ---------------------------------------------------------------------------------------

def candidates():
    """The possible Windows partitions on the machine (without mounting): [{device, label, size, locked}]"""
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-o", "PATH,FSTYPE,LABEL,SIZE,TYPE"],
                             capture_output=True, text=True, timeout=20).stdout
        devices = json.loads(out or "{}").get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found, stack = [], list(devices)
    while stack:
        dev = stack.pop(0)
        stack.extend(dev.get("children") or [])
        fstype = (dev.get("fstype") or "").lower()
        if dev.get("type") != "part" or int(dev.get("size") or 0) < MIN_NTFS_BYTES:
            continue
        if fstype in ("ntfs", "ntfs3", "bitlocker"):
            found.append({"device": dev["path"], "label": dev.get("label") or "", "size": int(dev["size"]),
                          "locked": fstype == "bitlocker"})
    return found


def _mountpoint(device):
    out = subprocess.run(["findmnt", "-nro", "TARGET", "--source", device], capture_output=True, text=True).stdout
    return out.split("\n")[0].strip()


def mount(device):
    """A read-only mount. -> (mount point, whether we mounted it); on error (None, False)"""
    current = _mountpoint(device)
    if current:
        return current, False
    r = subprocess.run(["udisksctl", "mount", "-b", device, "-o", "ro"], capture_output=True, text=True, timeout=120)
    current = _mountpoint(device)
    return (current, True) if r.returncode == 0 and current else (None, False)


def unmount(device):
    subprocess.run(["udisksctl", "unmount", "-b", device], capture_output=True, timeout=60)


# --- Survey ------------------------------------------------------------------------------------------

def _size(path):
    total = 0
    for root, dirs, files in os.walk(path):  # symbolic links (NTFS junctions) are not followed
        for name in files:
            p = os.path.join(root, name)
            if name.lower() in SKIP_FILES or name.lower().endswith(SKIP_SUFFIXES) or os.path.islink(p):
                continue
            try:
                total += os.stat(p).st_size
            except OSError:
                pass
    return total


def users(mnt):
    """The Windows users and the sizes of their folders. -> [] if this is not a Windows partition"""
    root = Path(mnt)
    if not (root / "Windows" / "System32").is_dir() or not (root / "Users").is_dir():
        return []
    result = []
    for home in sorted((root / "Users").iterdir()):
        if home.name.lower() in SKIP_USERS or not home.is_dir() or home.is_symlink():
            continue
        folders = {key: _size(home / win) for key, (win, _xdg) in FOLDERS.items() if (home / win).is_dir()}
        if not any(folders.values()):
            continue
        try:
            found = programs(root, home)
        except Exception:  # noqa: BLE001 (only an extra: the files can still be brought over)
            found = []
        result.append({"name": home.name, "home": str(home), "folders": folders,
                       "bookmarks": len(_bookmark_sources(home)), "programs": found})
    return result


# --- Programs used on Windows --------------------------------------------------------------------------

# A Start menu entry's or a folder's name (lower case) -> the wizard's app (sloth_welcome/catalog.py), and when that
# is not the same program but its Sloth OS counterpart, the Windows program's name ("instead of …"). The exact
# matches are tried first, so having both LibreOffice and Word gives LibreOffice once, as itself. Microsoft Edge is
# left out: it is on every Windows
PROGRAMS = [
    (r"\bfirefox\b", "org.mozilla.firefox", ""),
    (r"\bgoogle chrome\b", "com.google.Chrome", ""),
    (r"^brave\b|bravesoftware", "com.brave.Browser", ""),
    (r"^zen( browser)?$", "app.zen_browser.zen", ""),
    (r"^vivaldi\b", "com.vivaldi.Vivaldi", ""),
    (r"^opera( gx)?( browser| stable)?$", "com.opera.Opera", ""),
    (r"^librewolf\b", "io.gitlab.librewolf-community", ""),
    (r"^chromium$", "org.chromium.Chromium", ""),
    (r"^floorp\b", "one.ablaze.floorp", ""),
    (r"^tor browser\b", "org.torproject.torbrowser-launcher", ""),
    (r"^libreoffice\b", "org.libreoffice.LibreOffice", ""),
    (r"^onlyoffice\b", "org.onlyoffice.desktopeditors", ""),
    (r"^wps office\b", "com.wps.Office", ""),
    (r"^(mozilla )?thunderbird\b", "org.mozilla.Thunderbird", ""),
    (r"^obsidian$", "md.obsidian.Obsidian", ""),
    (r"^joplin$", "net.cozic.joplin_desktop", ""),
    (r"^bitwarden$", "com.bitwarden.desktop", ""),
    (r"^vlc( media player)?$|^videolan$", "org.videolan.VLC", ""),
    (r"^mpv$", "io.mpv.Mpv", ""),
    (r"^spotify$|^spotifyab\.spotifymusic_", "com.spotify.Client", ""),
    (r"^stremio\b", "com.stremio.Stremio", ""),
    (r"^plex( htpc)?$|^plexinc\.plexdesktop", "tv.plex.PlexDesktop", ""),
    (r"^jellyfin media player$", "com.github.iwalton3.jellyfin-media-player", ""),
    (r"^discord$|^discord inc$", "com.discordapp.Discord", ""),
    (r"^telegram( desktop)?$|^telegrammessengerllp\.telegramdesktop_", "org.telegram.desktop", ""),
    (r"^signal$", "org.signal.Signal", ""),
    (r"^zoom( workplace)?$", "us.zoom.Zoom", ""),
    (r"^slack( technologies)?$", "com.slack.Slack", ""),
    (r"^element$", "im.riot.Riot", ""),
    (r"^viber$", "com.viber.Viber", ""),
    (r"^steam$", "com.valvesoftware.Steam", ""),
    (r"^prism launcher$", "org.prismlauncher.PrismLauncher", ""),
    (r"^roblox studio$", "win.robloxstudio", ""),
    (r"^lutris$", "net.lutris.Lutris", ""),
    (r"^itch$", "io.itch.itch", ""),
    (r"^retroarch\b", "org.libretro.RetroArch", ""),
    (r"^battle\.net$", "win.battlenet", ""),
    (r"^ea( app)?$", "win.ea", ""),
    (r"^ubisoft connect$|^uplay$", "win.ubisoft", ""),
    (r"^rockstar games launcher$", "win.rockstar", ""),
    (r"^gimp\b", "org.gimp.GIMP", ""),
    (r"^krita\b", "org.kde.krita", ""),
    (r"^inkscape$", "org.inkscape.Inkscape", ""),
    (r"^kdenlive$", "org.kde.kdenlive", ""),
    (r"^obs studio$", "com.obsproject.Studio", ""),
    (r"^blender\b", "org.blender.Blender", ""),
    (r"^audacity$", "org.audacityteam.Audacity", ""),
    (r"^darktable$", "org.darktable.Darktable", ""),
    (r"^shotcut$", "org.shotcut.Shotcut", ""),
    # counterparts
    (r"^(word|excel|powerpoint)( \d{4})?$|^microsoft office\b", "org.libreoffice.LibreOffice", "Microsoft Office"),
    (r"^outlook( \(classic\))?$", "org.mozilla.Thunderbird", "Outlook"),
    (r"whatsapp", "com.rtosta.zapzap", "WhatsApp"),
    (r"^microsoft teams( classic| \(work or school\))?$|^msteams_", "com.github.IsmaelMartinez.teams_for_linux",
     "Microsoft Teams"),
    (r"^epic games launcher$", "com.heroicgameslauncher.hgl", "Epic Games"),
    (r"^gog galaxy\b", "com.heroicgameslauncher.hgl", "GOG Galaxy"),
    (r"^minecraft( launcher)?$", "org.prismlauncher.PrismLauncher", "Minecraft Launcher"),
    (r"^roblox player$", "org.vinegarhq.Sober", "Roblox"),
    (r"^(adobe )?photoshop\b", "org.gimp.GIMP", "Photoshop"),
    (r"^adobe illustrator\b", "org.inkscape.Inkscape", "Illustrator"),
    (r"^adobe premiere\b", "org.kde.kdenlive", "Premiere Pro"),
    (r"^adobe lightroom\b", "org.darktable.Darktable", "Lightroom"),
]
START_MENU = "ProgramData/Microsoft/Windows/Start Menu/Programs"
USER_START_MENU = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
# Microsoft Store apps have no Start menu shortcut; their package folders (e.g. SpotifyAB.SpotifyMusic_zpdnekdrzrea0)
STORE_APPS = ("Program Files/WindowsApps", "AppData/Local/Packages")


def _program_names(root, home):
    names = set()
    for base in (Path(root) / START_MENU, Path(home) / USER_START_MENU):
        for _dirpath, dirs, files in os.walk(base):
            names.update(d.lower() for d in dirs)
            names.update(f[:-4].lower() for f in files if f.lower().endswith(".lnk"))
    for base in (Path(root) / STORE_APPS[0], Path(home) / STORE_APPS[1]):
        try:
            names.update(p.name.lower() for p in base.iterdir())
        except OSError:
            pass
    return names


def programs(root, home):
    """The wizard's apps that match the programs of this Windows account. -> [{id, instead}] ("instead": the Windows
    program's name if the app is its counterpart, "" if it is the same program)"""
    names = _program_names(root, home)
    found = {}
    for pattern, app_id, instead in sorted(PROGRAMS, key=lambda p: bool(p[2])):  # the exact matches first
        if app_id not in found and any(re.search(pattern, n) for n in names):
            found[app_id] = instead
    order = {app_id: i for i, (_p, app_id, _i) in enumerate(PROGRAMS)}
    return [{"id": app_id, "instead": instead} for app_id, instead in sorted(found.items(), key=lambda x: order[x[0]])]


# --- Steam games -----------------------------------------------------------------------------------------

# Where Windows' Steam and its libraries usually are on a drive; plus what Steam's libraryfolders.vdf names
STEAM_DIRS = ("Program Files (x86)/Steam", "Program Files/Steam", "SteamLibrary", "Steam", "Games/Steam",
              "Games/SteamLibrary", "Program Files (x86)/SteamLibrary")
SKIP_APPIDS = {"228980"}  # Steamworks Common Redistributables: Steam installs it itself


def _steam_library_paths(mounts):
    """The libraries Windows' Steam knows about, without the drive letter (D:\\Games\\Steam -> Games/Steam): the
    letter says nothing on Linux, so every Windows drive is looked at."""
    found = []
    for mnt in mounts:
        for d in STEAM_DIRS[:2]:
            try:
                text = (Path(mnt) / d / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            folders = steam.ci(steam.vdf_load(text), "libraryfolders") or {}
            for v in folders.values():
                path = steam.ci(v, "path") if isinstance(v, dict) else None
                if path:
                    found.append(re.sub(r"^[A-Za-z]:[\\/]*", "", path).replace("\\", "/").strip("/"))
    return found


def steam_games(mounts):
    """The fully installed Steam games on the Windows drives. -> [{appid, name, size, manifest, dir, installdir}]"""
    rels = list(dict.fromkeys(list(STEAM_DIRS) + _steam_library_paths(mounts)))
    games = {}
    for mnt in mounts:
        for rel in rels:
            apps = Path(mnt) / rel / "steamapps"
            if not rel or not apps.is_dir():
                continue
            for acf in sorted(apps.glob("appmanifest_*.acf")):
                try:
                    state = steam.ci(steam.vdf_load(acf.read_text(encoding="utf-8", errors="replace")), "AppState") or {}
                except OSError:
                    continue
                appid, installdir = steam.ci(state, "appid") or "", steam.ci(state, "installdir") or ""
                if (not appid or appid in SKIP_APPIDS or appid in games or steam.ci(state, "StateFlags") != "4"
                        or not installdir or "/" in installdir or installdir in (".", "..")):
                    continue
                folder = apps / "common" / installdir
                if not folder.is_dir() or folder.is_symlink():
                    continue
                games[appid] = {"appid": appid, "name": steam.ci(state, "name") or installdir, "size": _size(folder),
                                "manifest": str(acf), "dir": str(folder), "installdir": installdir}
    return sorted(games.values(), key=lambda g: g["name"].lower())


def steam_running():
    """Steam rewrites its settings (config.vdf) when it exits, so it must be closed while games come over."""
    try:
        return subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode == 0
    except OSError:
        return False


# --- Steam games: Proton instead of a Linux version ------------------------------------------------------

STORE_API = "https://store.steampowered.com/api/appdetails?appids={appid}&filters=platforms"
USER_AGENT = "Sloth-OS (https://github.com/Sloth-OS-Linux/sloth-os)"
DEFAULT_TOOL = "proton_experimental"


def _fetch(url, timeout):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def has_linux_version(appid):
    """Whether the game also has a Linux version (Steam's store). None: unknown (offline)."""
    try:
        data = json.loads(_fetch(STORE_API.format(appid=appid), 15))
        entry = data.get(str(appid)) or {}
        if not entry.get("success"):
            return None
        return bool((entry.get("data") or {}).get("platforms", {}).get("linux"))
    except Exception:  # noqa: BLE001 (offline, a changed answer: Steam then decides itself)
        return None


def force_proton(root, appids):
    """Steam's "Force the use of a specific compatibility tool" for these games (config.vdf, CompatToolMapping):
    a game with a Linux version would otherwise download that one instead of using the Windows files that came
    over. The tool is the one Steam uses for every other game if that is set, else Proton Experimental (Steam
    downloads it at the first start). Steam must be closed. -> the number of games set"""
    path = Path(root) / "config" / "config.vdf"
    try:
        data = steam.vdf_load(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        data = {}
    node = data
    for key in ("InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"):
        child = steam.ci(node, key)
        if not isinstance(child, dict):
            child = node[key] = {}
        node = child
    default = steam.ci(steam.ci(node, "0"), "name") or DEFAULT_TOOL
    count = 0
    for appid in appids:
        if str(appid) in node:
            continue  # the user's own choice stays
        node[str(appid)] = {"name": default, "config": "", "priority": "250"}
        count += 1
    if count:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".sloth-tmp")
        tmp.write_text(steam.vdf_dump(data) + "\n", encoding="utf-8")
        tmp.replace(path)
    return count


# --- Steam games: saves kept on the computer ----------------------------------------------------------

# Where games keep their saves (PCGamingWiki's data, the list Ludusavi uses; downloaded when needed, ~18 MB)
SAVES_MANIFEST = "https://raw.githubusercontent.com/mtkennerly/ludusavi-manifest/master/data/manifest.yaml"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "ludusavi-manifest.yaml"
# The Windows folders a save can be in (from the user's folder) and their place in a Proton environment
SAVE_ROOTS = {"<home>": "", "<winAppData>": "AppData/Roaming", "<winLocalAppData>": "AppData/Local",
              "<winDocuments>": "Documents"}
SAVE_LIMIT = 4 * 1024**3   # a "save" folder bigger than this per game is left out (videos, mods)


def _saves_manifest():
    try:
        if CACHE.is_file() and time.time() - CACHE.stat().st_mtime < 7 * 86400:
            return CACHE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    try:
        text = _fetch(SAVES_MANIFEST, 120).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 (offline: no saves, the games still come over)
        return ""
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(text, encoding="utf-8")
    except OSError:
        pass
    return text


def _unquote_yaml(key):
    key = key.strip()
    if len(key) >= 2 and key[0] == key[-1] == '"':
        return key[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(key) >= 2 and key[0] == key[-1] == "'":
        return key[1:-1].replace("''", "'")
    return key


def _parse_game(block):
    """One game of the manifest (YAML, written by a tool, so its layout is fixed). -> (Steam Cloud, [save paths])"""
    lines = block.split("\n")
    cloud, saves, section = False, [], ""
    entry, tags, whens, when = None, [], [], None

    def flush():
        if entry is None:
            return
        if when is not None:
            whens.append(when)
        windows = not whens or any(w.get("os") in (None, "windows") and w.get("store") in (None, "steam")
                                   for w in whens)
        if "save" in tags and windows:
            saves.append(entry)

    sub = ""
    for line in lines[1:]:
        indent = len(line) - len(line.lstrip(" "))
        text = line.strip()
        if not text:
            continue
        if indent == 2:
            if section == "files":
                flush()
                entry = None
            section = text.rstrip(":")
            continue
        if section == "cloud" and indent == 4 and text.replace(" ", "") == "steam:true":
            cloud = True
        if section != "files":
            continue
        if indent == 4:
            flush()
            entry, tags, whens, when, sub = _unquote_yaml(text[:-1] if text.endswith(":") else text), [], [], None, ""
        elif indent == 6:
            sub = text.rstrip(":")
            if when is not None:
                whens.append(when)
                when = None
        elif indent >= 8 and sub == "tags" and text.startswith("- "):
            tags.append(text[2:].strip())
        elif indent >= 8 and sub == "when":
            if text.startswith("- "):
                if when is not None:
                    whens.append(when)
                when = {}
                text = text[2:]
            if ":" in text and when is not None:
                k, v = text.split(":", 1)
                when[k.strip()] = v.strip()
    if section == "files":
        flush()
    return cloud, saves


def save_locations(text, appids):
    """The manifest's games by Steam ID. -> {appid: (Steam Cloud, [save paths])}"""
    wanted, found = {str(a) for a in appids}, {}
    for m in re.finditer(r"^  steam:\n    id: (\d+)$", text, re.M):
        appid = m.group(1)
        if appid not in wanted or appid in found:
            continue
        start = text.rfind("\n", 0, text.rfind("\n", 0, m.start()))  # back to the game's own line
        while start > 0 and text[start + 1:start + 2] == " ":
            start = text.rfind("\n", 0, start)
        nxt = re.compile(r"^\S", re.M).search(text, m.end())
        found[appid] = _parse_game(text[start + 1:nxt.start() if nxt else len(text)])
    return found


def _ci_pattern(rel):
    """NTFS ignores the case of names, Linux does not: "AppData/locallow" must find "AppData/LocalLow"."""
    out, in_class = [], False
    for c in rel:
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        out.append(f"[{c.lower()}{c.upper()}]" if c.isalpha() and not in_class and c.lower() != c.upper() else c)
    return "".join(out)


def _copy_new(src, dest):
    """A file or a folder, without overwriting anything already there. -> bytes copied"""
    total = 0
    pairs = [(src, dest)] if src.is_file() else [
        (Path(r, f), dest / Path(r, f).relative_to(src)) for r, _d, files in os.walk(src) for f in files]
    for s, d in pairs:
        if s.is_symlink() or d.exists():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        total += s.stat().st_size
    return total


def copy_saves(win_home, games, root=None, manifest_text=None):
    """The saves the games kept on Windows (not in Steam Cloud) into each game's Proton environment, where the
    game looks for them (steamapps/compatdata/<appid>/pfx/drive_c/users/steamuser/…). Proton fills in the rest of
    the environment at the first start without touching what is there (Steam drops its cloud files there the same
    way). Nothing already there is overwritten. -> [names of the games whose saves came over]"""
    import glob
    text = _saves_manifest() if manifest_text is None else manifest_text
    if not text or not win_home:
        return []
    win_home = Path(win_home)
    # Documents may have been moved into OneDrive by Windows
    documents = [win_home / "Documents"] + sorted(p for p in win_home.glob("OneDrive*/Documents") if p.is_dir())
    locations = save_locations(text, [g["appid"] for g in games])
    done = []
    for g in games:
        cloud, paths = locations.get(g["appid"], (False, []))
        if cloud or not paths:
            continue  # Steam Cloud brings them itself (copying too could ask which one to keep)
        user = Path(root or steam_target()) / "steamapps" / "compatdata" / g["appid"] / "pfx" / "drive_c" / "users" / "steamuser"
        plan = []
        for path in paths:
            prefix = next((p for p in SAVE_ROOTS if path.startswith(p + "/")), None)
            # a folder named after the Steam account's number (e.g. EldenRing/7656119…): whichever is there
            rest = path[len(prefix) + 1:].replace("<storeUserId>", "*") if prefix else ""
            if not prefix or "<" in rest or ".." in rest.split("/"):
                continue  # in the game's folder (already here), Steam's own folder, other users' places
            bases = [(d, "Documents") for d in documents] if prefix == "<winDocuments>" else \
                [(win_home / SAVE_ROOTS[prefix], SAVE_ROOTS[prefix])]
            for base, target in bases:
                for match in glob.glob(glob.escape(str(base)) + "/" + _ci_pattern(rest), recursive=True):
                    m = Path(match)
                    plan.append((m, user / target / m.relative_to(base)))
        size = 0
        for src, _dest in plan:
            size += src.stat().st_size if src.is_file() else _size(src)
        if not plan or size > SAVE_LIMIT:
            continue
        try:
            for src, dest in plan:
                _copy_new(src, dest)
        except OSError:
            continue
        done.append(g["name"])
    return done


def finish_games(games, win_home, root=None):
    """After copying: the games now in Steam here get Proton where Steam would download a Linux version instead,
    and their saves kept on Windows. Both need the internet; offline Steam decides itself and the saves stay on
    Windows. -> {"proton": count, "saves": [names]}"""
    root = Path(root or steam_target())
    here = [g for g in games if (root / "steamapps" / f"appmanifest_{g['appid']}.acf").exists()]
    out = {"proton": 0, "saves": []}
    try:
        linux = [g["appid"] for g in here if has_linux_version(g["appid"])]
        out["proton"] = force_proton(root, linux) if linux else 0
    except OSError:
        pass
    try:
        out["saves"] = copy_saves(win_home, here, root)
    except OSError:
        pass
    return out


def steam_target():
    """Sloth OS's Steam library: the one in use, or the Flatpak Steam's own (Steam may not be installed yet: it
    finds the games in its folder at its first start)."""
    return steam.steam_root() or steam.FLATPAK_ROOT


def copy_games(games, root=None, on_progress=lambda done, total, name: None, cancelled=lambda: False):
    """Copies the games into Steam's own library (steamapps/common/<installdir>); a game's manifest is written only
    when all its files are there, so an interrupted copy shows no broken game, and continues where it stopped.
    -> {"games": count, "skipped": count, "failed": [name], "bytes": bytes}"""
    apps = Path(root or steam_target()) / "steamapps"
    plan, todo, stats = [], [], {"games": 0, "skipped": 0, "failed": [], "bytes": 0}
    for g in games:
        if (apps / f"appmanifest_{g['appid']}.acf").exists():
            stats["skipped"] += 1  # already in Steam here
            continue
        todo.append(g)
        src_root, dest_root = Path(g["dir"]), apps / "common" / g["installdir"]
        for dirpath, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(dirpath, d))]
            for name in files:
                src = Path(dirpath, name)
                if src.is_symlink():
                    continue
                try:
                    plan.append((g["appid"], src, dest_root / src.relative_to(src_root), src.stat().st_size))
                except OSError:
                    pass
    total = sum(p[3] for p in plan)
    done, last, broken = 0, 0.0, set()
    for appid, src, dest, size in plan:
        if cancelled():
            break
        try:
            if not (dest.is_file() and dest.stat().st_size == size):
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_name(f".{dest.name}.sloth-part")
                shutil.copyfile(src, tmp)
                shutil.copystat(src, tmp)
                tmp.replace(dest)
                stats["bytes"] += size
        except OSError:
            broken.add(appid)
        done += size
        now = time.monotonic()
        if now - last > 0.2:
            on_progress(done, total, src.name)
            last = now
    on_progress(done, total, "")
    if cancelled():
        return stats
    for g in todo:
        if g["appid"] in broken:
            stats["failed"].append(g["name"])
            continue
        try:
            shutil.copyfile(g["manifest"], apps / f"appmanifest_{g['appid']}.acf")
            stats["games"] += 1
        except OSError:
            stats["failed"].append(g["name"])
    return stats


# --- Copying -------------------------------------------------------------------------------------------

def target_dir(key):
    xdg = FOLDERS[key][1]
    try:
        out = subprocess.run(["xdg-user-dir", xdg], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    if out and out != str(Path.home()):
        return Path(out)
    return Path.home() / FOLDERS[key][0]


def _already_copied(dest, size):
    """Whether this file is already there: under the same name, or with a "(Windows)" suffix from an earlier copy."""
    if dest.exists() and dest.stat().st_size == size:
        return True
    return any(p.stat().st_size == size for p in dest.parent.glob(f"{_glob_escape(dest.stem)} (Windows*){_glob_escape(dest.suffix)}")
               if p.is_file())


def _glob_escape(text):
    return "".join(f"[{c}]" if c in "*?[" else c for c in text)


def _free_name(dest):
    if not dest.exists():
        return dest
    n = 1
    while True:
        cand = dest.with_name(f"{dest.stem} (Windows{'' if n == 1 else f' {n}'}){dest.suffix}")
        if not cand.exists():
            return cand
        n += 1


def copy(home, keys, on_progress=lambda done, total, name: None, cancelled=lambda: False):
    """Copies the chosen folders. -> {"copied": count, "skipped": count, "failed": [path], "bytes": bytes}

    Whatever is already there with the same size is skipped; a file with the same name but other contents gets a "(Windows)" suffix.
    """
    home = Path(home)
    plan = []
    for key in keys:
        src_root = home / FOLDERS[key][0]
        dest_root = target_dir(key)
        for root, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for name in files:
                src = Path(root, name)
                if name.lower() in SKIP_FILES or name.lower().endswith(SKIP_SUFFIXES) or src.is_symlink():
                    continue
                try:
                    plan.append((src, dest_root / src.relative_to(src_root), src.stat().st_size))
                except OSError:
                    pass
    total = sum(size for _s, _d, size in plan)
    done, stats = 0, {"copied": 0, "skipped": 0, "failed": [], "bytes": 0}
    last = 0.0
    for src, dest, size in plan:
        if cancelled():
            break
        try:
            if dest.parent.is_dir() and _already_copied(dest, size):
                stats["skipped"] += 1
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                target = _free_name(dest) if dest.exists() else dest
                tmp = target.with_name(f".{target.name}.sloth-part")
                shutil.copyfile(src, tmp)
                shutil.copystat(src, tmp)
                tmp.replace(target)
                stats["copied"] += 1
                stats["bytes"] += size
        except OSError:
            stats["failed"].append(str(src))
        done += size
        now = time.monotonic()
        if now - last > 0.2:
            on_progress(done, total, src.name)
            last = now
    on_progress(done, total, "")
    return stats


# --- Bookmarks ---------------------------------------------------------------------------------------

def _bookmark_sources(home):
    found = []
    for browser, base in CHROMIUM_BROWSERS.items():
        for f in sorted((home / base).glob("*/Bookmarks")):
            found.append((browser, "chromium", f))
    for f in sorted((home / FIREFOX_PROFILES).glob("*/places.sqlite")):
        found.append(("Firefox", "firefox", f))
    return found


def _chromium_tree(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    roots = data.get("roots", {})

    def node(n):
        if n.get("type") == "url":
            return {"title": n.get("name", ""), "url": n.get("url", "")}
        return {"title": n.get("name", ""), "children": [node(c) for c in n.get("children", [])]}

    return [node(roots[k]) for k in ("bookmark_bar", "other", "synced") if k in roots]


def _firefox_tree(path):
    # the browser may lock the file: we read from a copy
    with tempfile.TemporaryDirectory() as tmp:
        copy_path = Path(tmp) / "places.sqlite"
        shutil.copyfile(path, copy_path)
        con = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
        rows = con.execute("SELECT b.id, b.parent, b.type, b.title, p.url FROM moz_bookmarks b "
                           "LEFT JOIN moz_places p ON b.fk = p.id ORDER BY b.parent, b.position").fetchall()
        con.close()
    children = {}
    for bid, parent, kind, title, url in rows:
        children.setdefault(parent, []).append((bid, kind, title or "", url))

    def build(bid, title):
        items = []
        for cid, kind, ctitle, url in children.get(bid, []):
            if kind == 1 and url and not url.startswith("place:"):
                items.append({"title": ctitle, "url": url})
            elif kind == 2:
                items.append(build(cid, ctitle))
        return {"title": title, "children": items}

    # 1 = root; below it the menu, the toolbar and the other bookmarks' folders (with internal names)
    names = {"menu": "Bookmarks Menu", "toolbar": "Bookmarks Toolbar", "unfiled": "Other Bookmarks",
             "mobile": "Mobile Bookmarks"}
    return [build(cid, names.get(ctitle, ctitle)) for cid, kind, ctitle, _u in children.get(1, []) if kind == 2]


def _html(nodes, depth=1):
    pad = "    " * depth
    out = [f"{pad}<DL><p>"]
    for n in nodes:
        if "url" in n:
            out.append(f'{pad}    <DT><A HREF="{html.escape(n["url"], quote=True)}">{html.escape(n["title"])}</A>')
        elif n.get("children"):
            out.append(f"{pad}    <DT><H3>{html.escape(n['title'])}</H3>")
            out.extend(_html(n["children"], depth + 1))
    out.append(f"{pad}</DL><p>")
    return out


def export_bookmarks(home, dest):
    """The Windows browsers' bookmarks into one HTML file (Netscape format). -> the number of bookmarks"""
    folders = []
    for browser, kind, path in _bookmark_sources(Path(home)):
        try:
            tree = _chromium_tree(path) if kind == "chromium" else _firefox_tree(path)
        except (OSError, ValueError, sqlite3.Error):
            continue
        label = browser if len([s for s in _bookmark_sources(Path(home)) if s[0] == browser]) == 1 \
            else f"{browser} ({path.parent.name})"
        folders.append({"title": label, "children": tree})

    def count(nodes):
        return sum(1 if "url" in n else count(n.get("children", [])) for n in nodes)

    total = count(folders)
    if not total:
        return 0
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
             '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
             "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>"] + _html(folders, 0)
    dest = _free_name(Path(dest)) if Path(dest).exists() else Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return total
