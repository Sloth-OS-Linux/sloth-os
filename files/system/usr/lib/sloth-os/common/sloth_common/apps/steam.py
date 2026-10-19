"""A Steam fájljai (csak olvasva): játékok, a Steamhez hozzáadott (nem Steames) programok, Proton-környezetek.

A Steamben hozzáadott Windows-programokat (pl. egy kézzel felvett Battle.net) kétféleképpen vehetjük át:
  - „Steamen keresztül” (link): a Sloth csak bejegyzést készít, a Steam indítja a saját beállításaival;
    a Steam fájljaihoz nem nyúlunk.
  - „Átvétel” (adopt): a program Windows-környezetéről másolat készül a Sloth könyvtárába (Btrfs-en
    reflinkkel: pillanatok alatt, szinte hely nélkül), és onnan a Sloth indítja. A Steam példánya
    érintetlen marad. A Steam környezetét sosem indítjuk a Sloth futtatójával (más Proton-verzió
    frissíthetné, és utána a Steamből már nem indulna).
"""
import logging
import re
import struct
import subprocess
from pathlib import Path

from . import library, menu

log = logging.getLogger("sloth-os.apps")

HOME = Path.home()
FLATPAK_ROOT = HOME / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
STEAM_ROOTS = [FLATPAK_ROOT, HOME / ".local/share/Steam", HOME / ".steam/steam"]


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
            if len(stack) > 1:
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
        q = lambda x: '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'  # noqa: E731
        if isinstance(v, dict):
            out.append("\t" * indent + q(k))
            out.append("\t" * indent + "{")
            out.append(vdf_dump(v, indent + 1))
            out.append("\t" * indent + "}")
        else:
            out.append("\t" * indent + q(k) + "\t\t" + q(v))
    return "\n".join(x for x in out if x)


def ci(d, key):
    """A Steam fájljaiban a kulcsok kis- és nagybetűje változhat."""
    if not isinstance(d, dict):
        return None
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return None


# --- A bináris VDF (shortcuts.vdf) -------------------------------------------------------------

def binary_vdf_load(data):
    """A Steam bináris VDF-je: 0x00 szótár, 0x01 szöveg, 0x02 32 bites szám, 0x08 szótár vége."""
    pos = 0

    def cstr():
        nonlocal pos
        end = data.index(b"\x00", pos)
        s = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return s

    def node():
        nonlocal pos
        out = {}
        while pos < len(data):
            kind = data[pos]
            pos += 1
            if kind == 0x08:
                return out
            key = cstr()
            if kind == 0x00:
                out[key] = node()
            elif kind == 0x01:
                out[key] = cstr()
            elif kind == 0x02:
                out[key] = struct.unpack_from("<i", data, pos)[0]
                pos += 4
            elif kind == 0x07:  # 64 bites szám (ritka)
                out[key] = struct.unpack_from("<q", data, pos)[0]
                pos += 8
            else:
                raise ValueError(f"ismeretlen VDF típus: {kind}")
        return out

    return node()


# --- Steam -----------------------------------------------------------------------------------

def steam_root():
    return next((r for r in STEAM_ROOTS if (r / "steamapps").is_dir()), None)


def is_flatpak(root):
    return root is not None and Path(root) == FLATPAK_ROOT


def library_folders(root):
    out = [root]
    try:
        folders = ci(vdf_load((root / "steamapps/libraryfolders.vdf").read_text(errors="replace")),
                     "libraryfolders") or {}
        out += [Path(ci(v, "path")) for v in folders.values() if isinstance(v, dict) and ci(v, "path")]
    except OSError:
        pass
    return list(dict.fromkeys(out))


def compat_tools(root):
    """Melyik programhoz melyik Proton van beállítva: {appid: név}."""
    try:
        data = vdf_load((root / "config/config.vdf").read_text(errors="replace"))
    except OSError:
        return {}
    node = data
    for key in ("InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"):
        node = ci(node, key) or {}
    return {k: ci(v, "name") or "" for k, v in node.items() if isinstance(v, dict)}


def _unquote(s):
    s = (s or "").strip()
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] == '"' else s


def shortcuts():
    """A Steamhez hozzáadott Windows-programok (minden Steam-fiókból):
    [{"appid", "gameid", "name", "exe", "start_dir", "options", "prefix", "proton", "icon", "flatpak"}]
    """
    root = steam_root()
    if not root:
        return []
    tools = compat_tools(root)
    out, seen = [], set()
    for path in sorted((root / "userdata").glob("*/config/shortcuts.vdf")):
        try:
            data = binary_vdf_load(path.read_bytes())
        except (OSError, ValueError, struct.error, IndexError) as e:
            log.warning("shortcuts.vdf (%s): %s", path, e)
            continue
        for sc in (ci(data, "shortcuts") or {}).values():
            if not isinstance(sc, dict):
                continue
            exe = Path(_unquote(ci(sc, "Exe")))
            appid = (ci(sc, "appid") or 0) & 0xFFFFFFFF
            if exe.suffix.lower() not in (".exe", ".msi", ".bat", ".lnk") or not appid or appid in seen:
                continue
            seen.add(appid)
            prefix = next((lib / f"steamapps/compatdata/{appid}/pfx" for lib in library_folders(root)
                           if (lib / f"steamapps/compatdata/{appid}/pfx/drive_c").is_dir()), None)
            icon = Path(_unquote(ci(sc, "icon"))) if ci(sc, "icon") else None
            out.append({
                "appid": appid,
                "gameid": (appid << 32) | 0x02000000,  # steam://rungameid/<ez> indítja
                "name": ci(sc, "AppName") or ci(sc, "appname") or exe.stem,
                "exe": exe,
                "start_dir": Path(_unquote(ci(sc, "StartDir"))) if ci(sc, "StartDir") else exe.parent,
                "options": ci(sc, "LaunchOptions") or "",
                "prefix": prefix,
                "proton": tools.get(str(appid), ""),
                "icon": icon if icon and icon.is_file() else None,
                "flatpak": is_flatpak(root),
            })
    return sorted(out, key=lambda s: s["name"].lower())


def imported(appid):
    """Átvettük-e már ezt a Steames programot (bármelyik módon)."""
    return next((a for a in library.all_apps() if (a.meta.get("steam") or {}).get("appid") == appid), None)


def can_adopt(sc):
    """Átvehető-e: van saját Windows-környezete, és a program abban van."""
    if not sc["prefix"]:
        return False
    try:
        sc["exe"].relative_to(sc["prefix"])
        return True
    except ValueError:
        return False


def _steam_info(sc):
    return {"appid": sc["appid"], "gameid": sc["gameid"], "proton": sc["proton"], "options": sc["options"],
            "flatpak": sc["flatpak"], "exe": str(sc["exe"]), "prefix": str(sc["prefix"] or "")}


def link(sc):
    """„Steamen keresztül”: bejegyzés a Sloth-ban és a Start menüben; a Steam fájljai érintetlenek."""
    app = library.create(sc["name"], kind="steam", steam=_steam_info(sc))
    icon = None
    if sc["icon"]:
        icon = sc["icon"]
    elif sc["exe"].is_file():
        icon = menu.extract_icon(sc["exe"], app.icons / "steam.png")
    menu.add_steam(app, sc["name"], sc["gameid"], icon, sc["flatpak"])
    app.set_folder_icon(icon)
    return app


def prefix_in_use(prefix):
    """Fut-e valami a Steam környezetében (akkor nem másolunk: a másolat félkész lehetne)."""
    marker = str(Path(prefix).parent).encode()
    for proc in Path("/proc").iterdir() if Path("/proc").is_dir() else []:
        if not proc.name.isdigit():
            continue
        try:
            if marker in (proc / "environ").read_bytes():
                return True
        except OSError:
            continue
    return False


def adopt(sc, files_label):
    """„Átvétel”: a Windows-környezet másolata a Sloth könyvtárába, onnan a Sloth indítja.

    -> az új App, vagy None (nem átvehető, vagy a másolás nem sikerült; ilyenkor semmi nem marad utána).
    """
    if not can_adopt(sc) or prefix_in_use(sc["prefix"]):
        return None
    library_dir = library.default_library()
    if not library.supported_location(library_dir):
        return None
    app = library.create(sc["name"], steam=_steam_info(sc), adopted=True)
    try:
        app.prefix.mkdir(parents=True)
        subprocess.run(["cp", "-a", "--reflink=auto", f"{sc['prefix']}/.", str(app.prefix)], check=True,
                       capture_output=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("átvétel (%s): %s", sc["name"], e)
        library.remove(app)
        return None
    exe = app.prefix / sc["exe"].relative_to(sc["prefix"])
    install_dir = app.host_to_windows(exe.parent)
    app.save_meta(install_dir=install_dir or "")
    menu.add(app, sc["name"], exe)
    app.link_files(exe.parent, files_label)
    icon = next((e["icon"] for e in menu.entries(app) if e["icon"].startswith("/")), None)
    app.set_folder_icon(icon)
    return app


def launch_command(app):
    """A Steamen keresztül átvett program indítóparancsa."""
    info = app.meta.get("steam") or {}
    url = f"steam://rungameid/{info.get('gameid')}"
    return ["flatpak", "run", "com.valvesoftware.Steam", url] if info.get("flatpak") else ["steam", url]
