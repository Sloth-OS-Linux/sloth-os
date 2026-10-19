"""Máshol telepített Windows-programok átvétele, újratelepítés nélkül.

Források: a Steamhez kézzel hozzáadott programok, a Lutris, a Bottles, és a korábbi, sima Wine-os
telepítések (~/.wine). Két mód van:
  - „Az eredeti programmal” (link): a Sloth csak bejegyzést készít (a listában és a Start menüben), a
    programot az indítja, ami eddig (Steam, Lutris, Bottles). Az eredeti fájlokhoz nem nyúlunk.
  - „Átvétel” (adopt): a program Windows-környezetéről másolat készül a Sloth könyvtárába (Btrfs-en
    reflinkkel: pillanatok alatt, szinte hely nélkül), és onnan a Sloth indítja. Az eredeti érintetlen.
Egy másik program Windows-környezetét sosem indítjuk a saját futtatónkkal: más Proton- vagy
Wine-verzió frissíthetné, és utána az eredeti helyén már nem indulna.
"""
import logging
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import detect, library, menu, steam

log = logging.getLogger("sloth-os.apps")

HOME = Path.home()
LUTRIS_DATA = [HOME / ".local/share/lutris", HOME / ".var/app/net.lutris.Lutris/data/lutris"]
LUTRIS_CONFIG = [HOME / ".config/lutris", HOME / ".var/app/net.lutris.Lutris/config/lutris"]
BOTTLES_ROOTS = [HOME / ".var/app/com.usebottles.bottles/data/bottles/bottles", HOME / ".local/share/bottles/bottles"]
WINE_PREFIX = HOME / ".wine"


@dataclass
class Found:
    source: str              # "steam" | "lutris" | "bottles" | "wine"
    id: str                  # a forráson belül egyedi
    name: str
    exe: Path                # a program indítófájlja
    prefix: Path | None      # a Windows-környezete (ha van saját)
    command: list | None     # amivel az eredeti program indítja (None: csak átvehető)
    icon: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self):
        return f"{self.source}:{self.id}"


# --- Egyszerű YAML (a Lutris és a Bottles gép által írt beállításfájljai) ----------------------------

def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        inner = v[1:-1]
        return inner.replace("''", "'") if v[0] == "'" else inner.replace('\\"', '"').replace("\\\\", "\\")
    return {"true": True, "false": False, "null": None, "~": None}.get(v.lower(), v) if v else ""


def simple_yaml(text):
    """Egymásba ágyazott kulcs: érték párok (a listákat és a többsoros értékeket kihagyja)."""
    root = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith(("#", "- ", "-\t")) or raw.strip() == "-":
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        m = re.match(r"^\s*('[^']*'|\"[^\"]*\"|[^:#]+?)\s*:(?:\s+(.*))?$", raw)
        if not m:
            continue
        key, value = _scalar(m.group(1)), (m.group(2) or "").strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1] if stack else root
        if value in ("", "|", ">", "|-", ">-"):
            node = {}
            parent[key] = node
            stack.append((indent, node))
        elif value.startswith(("[", "{")):
            parent[key] = value
        else:
            parent[key] = _scalar(value)
    return root


# --- Források ----------------------------------------------------------------------------------------

def _steam():
    out = []
    for sc in steam.shortcuts():
        out.append(Found("steam", str(sc["appid"]), sc["name"], sc["exe"], sc["prefix"],
                         steam.run_command(sc["gameid"], sc["flatpak"]), sc["icon"],
                         {"proton": sc["proton"], "options": sc["options"]}))
    return out


def _lutris_names(data_dir):
    """A Lutris játéklistája (pga.db): {beállításfájl neve: (azonosító, név)}"""
    db = data_dir / "pga.db"
    if not db.is_file():
        return {}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        rows = con.execute("SELECT id, name, configpath FROM games WHERE runner = 'wine' AND installed = 1").fetchall()
        con.close()
    except sqlite3.Error as e:
        log.warning("lutris: %s", e)
        return {}
    return {configpath: (gid, name) for gid, name, configpath in rows if configpath}


def _lutris():
    out = []
    for data_dir, config_dir in zip(LUTRIS_DATA, LUTRIS_CONFIG):
        names = _lutris_names(data_dir)
        flatpak = "net.lutris.Lutris" in str(data_dir)
        for games in (data_dir / "games", config_dir / "games"):
            for yml in sorted(games.glob("*.yml")) if games.is_dir() else []:
                if yml.stem not in names:
                    continue
                gid, name = names[yml.stem]
                try:
                    game = simple_yaml(yml.read_text(encoding="utf-8", errors="replace")).get("game") or {}
                except OSError:
                    continue
                exe = Path(str(game.get("exe") or ""))
                prefix = Path(str(game.get("prefix") or WINE_PREFIX))
                if exe.suffix.lower() != ".exe":
                    continue
                if not exe.is_absolute():
                    exe = prefix / exe
                cmd = ["flatpak", "run", "net.lutris.Lutris"] if flatpak else ["lutris"]
                out.append(Found("lutris", str(gid), name, exe, prefix if (prefix / "drive_c").is_dir() else None,
                                 cmd + [f"lutris:rungameid/{gid}"]))
    return out


def _bottles():
    out = []
    for root in BOTTLES_ROOTS:
        flatpak = "com.usebottles.bottles" in str(root)
        for cfg in sorted(root.glob("*/bottle.yml")) if root.is_dir() else []:
            try:
                bottle = simple_yaml(cfg.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            bottle_name = str(bottle.get("Name") or cfg.parent.name)
            prefix = cfg.parent
            for pid, prog in (bottle.get("External_Programs") or {}).items():
                if not isinstance(prog, dict) or prog.get("removed"):
                    continue
                exe = Path(str(prog.get("path") or ""))
                if exe.suffix.lower() != ".exe":
                    continue
                if not exe.is_absolute():
                    exe = prefix / exe
                name = str(prog.get("name") or exe.stem)
                cmd = (["flatpak", "run", "--command=bottles-cli", "com.usebottles.bottles"] if flatpak
                       else ["bottles-cli"]) + ["run", "-b", bottle_name, "-p", name]
                out.append(Found("bottles", f"{bottle_name}/{pid}", name, exe, prefix, cmd))
    return out


def _wine():
    """A korábbi, sima Wine-os telepítések (~/.wine): a felismert programok (registry, parancsikonok)."""
    env = library.WinEnv(WINE_PREFIX)
    if not env.exists():
        return []
    out = []
    for c in detect.detect(env).candidates:
        if c.checked and c.score >= 80:
            rel = str(c.path.relative_to(WINE_PREFIX))
            out.append(Found("wine", rel, c.name, c.path, WINE_PREFIX, None))
    return out


SOURCES = {"steam": _steam, "lutris": _lutris, "bottles": _bottles, "wine": _wine}


def found(sources=SOURCES):
    """Minden máshol telepített program, amit még nem vettünk át."""
    taken = {(a.meta.get("source") or {}).get("key") for a in library.all_apps()}
    out = []
    for name, fn in sources.items():
        try:
            out += [f for f in fn() if f.key not in taken]
        except Exception as e:  # egy forrás hibája ne akassza meg a többit
            log.warning("átvétel (%s): %s", name, e)
    return sorted(out, key=lambda f: (f.source, f.name.lower()))


def find(key):
    return next((f for f in found() if f.key == key), None)


def imported(key):
    """Átvettük-e már (bármelyik módon)."""
    return next((a for a in library.all_apps() if (a.meta.get("source") or {}).get("key") == key), None)


def can_link(f):
    return bool(f.command)


def can_adopt(f):
    """Átvehető-e: van saját Windows-környezete, és a program abban van."""
    if not f.prefix or not (f.prefix / "drive_c").is_dir():
        return False
    try:
        f.exe.relative_to(f.prefix)
        return True
    except ValueError:
        return False


def _source_info(f):
    return {"key": f.key, "from": f.source, "id": f.id, "exe": str(f.exe), "prefix": str(f.prefix or ""),
            **({"command": f.command} if f.command else {}), **f.extra}


def _icon(f, app):
    if f.icon and Path(f.icon).is_file():
        return f.icon
    if f.exe.is_file():
        return menu.extract_icon(f.exe, app.icons / f"{library.slugify(f.exe.stem)}.png")
    return None


def link(f):
    """„Az eredeti programmal”: bejegyzés a Sloth-ban és a Start menüben; az eredeti fájlok érintetlenek."""
    if not can_link(f):
        return None
    app = library.create(f.name, kind="link", source=_source_info(f))
    icon = _icon(f, app)
    menu.add_link(app, f.name, f.command, icon)
    app.set_folder_icon(icon)
    return app


def prefix_in_use(prefix):
    """Fut-e valami a Windows-környezetben (akkor nem másolunk: a másolat félkész lehetne)."""
    if not prefix:
        return False
    markers = [str(prefix).encode(), str(Path(prefix).parent).encode()]
    proc_root = Path("/proc")
    for proc in proc_root.iterdir() if proc_root.is_dir() else []:
        if not proc.name.isdigit():
            continue
        try:
            env = (proc / "environ").read_bytes()
        except OSError:
            continue
        for var in (b"WINEPREFIX=", b"STEAM_COMPAT_DATA_PATH="):
            for m in markers:
                if var + m + b"\0" in env or var + m + b"/pfx\0" in env:
                    return True
    return False


def adopt(f, files_label):
    """„Átvétel”: a Windows-környezet másolata a Sloth könyvtárába, onnan a Sloth indítja.

    -> az új App, vagy None (nem átvehető, vagy a másolás nem sikerült; ilyenkor semmi nem marad utána).
    """
    if not can_adopt(f) or prefix_in_use(f.prefix):
        return None
    if not library.supported_location(library.default_library()):
        return None
    app = library.create(f.name, source=_source_info(f), adopted=True)
    try:
        app.prefix.mkdir(parents=True)
        subprocess.run(["cp", "-a", "--reflink=auto", f"{f.prefix}/.", str(app.prefix)], check=True,
                       capture_output=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("átvétel (%s): %s", f.name, e)
        library.remove(app)
        return None
    exe = app.prefix / f.exe.relative_to(f.prefix)
    app.save_meta(install_dir=app.host_to_windows(exe.parent) or "")
    menu.add(app, f.name, exe)
    app.link_files(exe.parent, files_label)
    icon = next((e["icon"] for e in menu.entries(app) if e["icon"].startswith("/")), None)
    app.set_folder_icon(icon)
    return app


def launch_command(app):
    """A másik programmal indított („link”) program indítóparancsa."""
    cmd = (app.meta.get("source") or {}).get("command")
    return list(cmd) if isinstance(cmd, list) else None

