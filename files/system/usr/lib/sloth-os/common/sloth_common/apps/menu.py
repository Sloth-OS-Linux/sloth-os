"""A programok Start menü bejegyzései (~/.local/share/applications/sloth-win-*.desktop) és ikonjai.

Az indítást mindig a Sloth .exe kezelő végzi: Exec=sloth-exe --launch <program> <indítófájl>.
Az indítófájl a program Windows-környezetéhez képest relatív (drive_c/Program Files/…), így a
program mappája áthelyezhető; a környezeten kívüli fájl (pl. egy letöltött .exe) teljes úttal áll.
A máshonnan „az eredeti programmal” felvett programokat az indítja (pl. steam://rungameid/…, lutris:…).
"""
import configparser
import logging
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from .library import DATA_HOME, slugify

log = logging.getLogger("sloth-os.apps")

APPS_DIR = DATA_HOME / "applications"
GENERIC_ICON = "application-x-ms-dos-executable"


def extract_icon(exe, dest_png):
    """Ikon a .exe-ből (icoutils). Ha nem megy, None: az általános ikon marad."""
    dest_png = Path(dest_png)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ico = Path(tmp) / "icon.ico"
        try:
            with open(ico, "wb") as f:
                subprocess.run(["wrestool", "-x", "-t", "14", str(exe)], stdout=f,
                               stderr=subprocess.DEVNULL, timeout=20, check=True)
            if ico.stat().st_size == 0:
                return None
            subprocess.run(["icotool", "-x", "-o", tmp, str(ico)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        pngs = list(Path(tmp).glob("*.png"))
        if not pngs:
            return None

        def size(p):  # icon_1_256x256x32.png -> 256*32
            m = re.search(r"_(\d+)x(\d+)x(\d+)\.png$", p.name)
            return int(m.group(1)) * 100 + int(m.group(3)) if m else 0

        best = max(pngs, key=size)
        dest_png.write_bytes(best.read_bytes())
        return dest_png


def icon_path(app, exe):
    return app.icons / f"{slugify(Path(exe).stem)}.png"


def desktop_file_path(app, exe):
    return APPS_DIR / f"sloth-win-{app.id}-{slugify(Path(exe).stem)}.desktop"


def target(app, exe):
    """Az indítófájl a bejegyzésben: a Windows-környezeten belül relatív, kívül teljes út."""
    rel = os.path.relpath(exe, app.prefix)
    return str(exe) if rel.startswith("..") else rel


def _read(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
        return cp["Desktop Entry"]
    except (configparser.Error, KeyError, OSError, UnicodeDecodeError):
        return None


def entries(app):
    """A program Start menü bejegyzései: [{"desktop", "name", "icon", "target"}].

    target: az indítófájl (relatív a Windows-környezethez, vagy teljes út); máshonnan indítottnál "".
    """
    out = []
    for path in sorted(APPS_DIR.glob(f"sloth-win-{app.id}-*.desktop")):
        entry = _read(path)
        if entry is None or entry.get("X-Sloth-Program") != app.id:
            continue
        try:
            args = shlex.split(entry.get("Exec", ""))
        except ValueError:
            args = []
        target = args[3] if len(args) == 4 and args[1] == "--launch" else ""
        out.append({"desktop": path, "name": entry.get("Name", path.stem), "icon": entry.get("Icon", ""),
                    "target": target})
    return out


def _categories(app):
    # Felismert játék (umu / Steam adatbázis) a Játékok közé, minden más a Segédprogramok közé
    gameid = app.meta.get("gameid") or ""
    return "Game;" if app.meta.get("is_game") or (gameid and gameid != "umu-default") else "Utility;"


def _write(path, app, name, exec_line, icon, categories=None):
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={exec_line}\n"
        f"Icon={icon or GENERIC_ICON}\n"
        "Terminal=false\n"
        f"Categories={categories or _categories(app) + 'X-SlothWindowsProgram;'}\n"
        "StartupNotify=true\n"
        f"X-Sloth-Program={app.id}\n",
        encoding="utf-8")
    path.chmod(0o755)


def add(app, name, exe):
    """Start menü bejegyzés a program egyik indítófájljához."""
    icon = extract_icon(exe, icon_path(app, exe))
    path = desktop_file_path(app, exe)
    exec_line = " ".join(shlex.quote(a) for a in ["sloth-exe", "--launch", app.id, target(app, exe)])
    _write(path, app, name, exec_line, icon)
    return path


def add_command(app, name, command, icon=None, categories=None, args_placeholder=""):
    """Bejegyzés egy tetszőleges indítóparanccsal (pl. AppImage: sloth-exe --run <program> %U)."""
    path = APPS_DIR / f"sloth-win-{app.id}-app.desktop"
    exec_line = " ".join(shlex.quote(a) for a in command) + (f" {args_placeholder}" if args_placeholder else "")
    _write(path, app, name, exec_line, icon, categories)
    return path


def add_link(app, name, command, icon=None):
    """Máshol telepített program bejegyzése: az eredeti program indítja (Steam, Lutris, Bottles)."""
    path = APPS_DIR / f"sloth-win-{app.id}-link.desktop"
    _write(path, app, name, " ".join(shlex.quote(a) for a in command), icon)
    return path


def remove_entries(app):
    for e in entries(app):
        try:
            Path(e["desktop"]).unlink()
        except OSError:
            pass


def set_category(app):
    """A kategória újraírása (pl. ha az első indításkor kiderült, hogy játék)."""
    for e in entries(app):
        path = Path(e["desktop"])
        try:
            text = path.read_text(encoding="utf-8")
            new = re.sub(r"(?m)^Categories=.*$", f"Categories={_categories(app)}X-SlothWindowsProgram;", text)
            if new != text:
                path.write_text(new, encoding="utf-8")
        except OSError as e:
            log.warning("kategória: %s", e)


def relink(app, old_prefix):
    """A mappa áthelyezése után: az ikonok és a környezeten kívüli indítófájlok útja.

    A Windows-környezeten belüli (relatív) indítófájlok érvényesek maradnak. Ha egy relatív út a régi
    környezeten kívülre mutatott (a régi .exe kezelő így írta a letöltött .exe-ket), teljes út lesz belőle.
    """
    for e in entries(app):
        path = Path(e["desktop"])
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        out = []
        for line in lines:
            if line.startswith("Icon=") and line[5:].startswith("/"):
                icon = app.icons / Path(line[5:]).name
                if icon.is_file():
                    line = f"Icon={icon}"
            elif line.startswith("Exec=") and e["target"].startswith(".."):
                absolute = os.path.normpath(os.path.join(old_prefix, e["target"]))
                args = ["sloth-exe", "--launch", app.id, absolute]
                line = "Exec=" + " ".join(shlex.quote(a) for a in args)
            out.append(line)
        try:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        except OSError as err:
            log.warning("bejegyzés frissítése: %s", err)
    icon = next((e["icon"] for e in entries(app) if e["icon"].startswith("/")), None)
    if icon:
        app.set_folder_icon(icon)
