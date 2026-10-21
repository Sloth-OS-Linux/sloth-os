"""Taking over Windows programs installed elsewhere, without reinstalling.

Sources: programs added to Steam by hand, Lutris, Bottles, and earlier plain-Wine
installs (~/.wine). There are two modes:
  - "With the original app" (link): Sloth only makes an entry (in the list and the Start menu), and the
    program is started by what started it so far (Steam, Lutris, Bottles). The original files are not touched.
  - "Take over" (adopt): a copy of the program's Windows environment is made in Sloth's library (with a reflink
    on Btrfs: in moments, with almost no space), and Sloth starts it from there. The original stays untouched.
We never start another app's Windows environment with our own runner: a different Proton or
Wine version could update it, and then it would no longer start in its original place.
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
    id: str                  # unique within the source
    name: str
    exe: Path                # the program's start file
    prefix: Path | None      # its Windows environment (if it has its own)
    command: list | None     # what the original app starts it with (None: can only be taken over)
    icon: Path | None = None
    extra: dict = field(default_factory=dict)

    @property
    def key(self):
        return f"{self.source}:{self.id}"


# --- Simple YAML (the machine-written settings files of Lutris and Bottles) ----------------------------

def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        inner = v[1:-1]
        return inner.replace("''", "'") if v[0] == "'" else inner.replace('\\"', '"').replace("\\\\", "\\")
    return {"true": True, "false": False, "null": None, "~": None}.get(v.lower(), v) if v else ""


def simple_yaml(text):
    """Nested key: value pairs (lists and multi-line values are skipped)."""
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


# --- Sources ----------------------------------------------------------------------------------------

def _steam():
    out = []
    for sc in steam.shortcuts():
        out.append(Found("steam", str(sc["appid"]), sc["name"], sc["exe"], sc["prefix"],
                         steam.run_command(sc["gameid"], sc["flatpak"]), sc["icon"],
                         {"proton": sc["proton"], "options": sc["options"]}))
    return out


def _lutris_names(data_dir):
    """Lutris' game list (pga.db): {settings file name: (ID, name)}"""
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
    """The earlier plain-Wine installs (~/.wine): the recognized programs (registry, shortcuts)."""
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
    """Every program installed elsewhere that we have not taken over yet."""
    taken = {(a.meta.get("source") or {}).get("key") for a in library.all_apps()}
    out = []
    for name, fn in sources.items():
        try:
            out += [f for f in fn() if f.key not in taken]
        except Exception as e:  # one source's error must not hold up the others
            log.warning("take over (%s): %s", name, e)
    return sorted(out, key=lambda f: (f.source, f.name.lower()))


def find(key):
    return next((f for f in found() if f.key == key), None)


def imported(key):
    """Whether we have taken it over already (in either mode)."""
    return next((a for a in library.all_apps() if (a.meta.get("source") or {}).get("key") == key), None)


def can_link(f):
    return bool(f.command)


def can_adopt(f):
    """Whether it can be taken over: it has its own Windows environment, and the program is in it."""
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
    """"With the original app": an entry in Sloth and in the Start menu; the original files stay untouched."""
    if not can_link(f):
        return None
    app = library.create(f.name, kind="link", source=_source_info(f))
    icon = _icon(f, app)
    menu.add_link(app, f.name, f.command, icon)
    app.set_folder_icon(icon)
    return app


def prefix_in_use(prefix):
    """Whether anything runs in the Windows environment (then we do not copy: the copy could be half-done)."""
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
    """"Take over": a copy of the Windows environment in Sloth's library, and Sloth starts it from there.

    -> the new App, or None (cannot be taken over, or the copy failed; then nothing is left behind).
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
        log.warning("take over (%s): %s", f.name, e)
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
    """The start command of a program started by another app ("link")."""
    cmd = (app.meta.get("source") or {}).get("command")
    return list(cmd) if isinstance(cmd, list) else None

