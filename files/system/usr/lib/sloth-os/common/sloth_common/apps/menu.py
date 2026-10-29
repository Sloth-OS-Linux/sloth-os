"""The programs' Start menu entries (~/.local/share/applications/sloth-win-*.desktop) and icons.

Starting is always done by the Sloth .exe handler: Exec=sloth-exe --launch <program> <start file>.
The start file is relative to the program's Windows environment (drive_c/Program Files/…), so the
program's folder can be moved; a file outside the environment (e.g. a downloaded .exe) has a full path.
Programs added from elsewhere "with the original app" are started by that app (e.g. steam://rungameid/…, lutris:…).
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
    """An icon from the .exe (icoutils). If that does not work, None: the generic icon stays."""
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
    """The start file in the entry: relative inside the Windows environment, a full path outside it."""
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
    """The program's Start menu entries: [{"desktop", "name", "icon", "target"}].

    target: the start file (relative to the Windows environment, or a full path); "" for one started elsewhere.
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
    # A recognized game (umu / Steam database) goes among Games, everything else among Utilities
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
    """A Start menu entry for one of the program's start files."""
    icon = extract_icon(exe, icon_path(app, exe))
    path = desktop_file_path(app, exe)
    exec_line = " ".join(shlex.quote(a) for a in ["sloth-exe", "--launch", app.id, target(app, exe)])
    _write(path, app, name, exec_line, icon)
    return path


def add_command(app, name, command, icon=None, categories=None, args_placeholder=""):
    """An entry with an arbitrary start command (e.g. AppImage: sloth-exe --run <program> %U)."""
    path = APPS_DIR / f"sloth-win-{app.id}-app.desktop"
    exec_line = " ".join(shlex.quote(a) for a in command) + (f" {args_placeholder}" if args_placeholder else "")
    _write(path, app, name, exec_line, icon, categories)
    return path


def add_link(app, name, command, icon=None):
    """An entry for a program installed elsewhere: the original app starts it (Steam, Lutris, Bottles)."""
    path = APPS_DIR / f"sloth-win-{app.id}-link.desktop"
    _write(path, app, name, " ".join(shlex.quote(a) for a in command), icon)
    return path


def url_handler_path(app):
    # not "sloth-win-<program>-…": it is not a Start menu entry (entries() does not list it)
    return APPS_DIR / f"sloth-url-{app.id}.desktop"


def register_url_handlers(app):
    """The link types the program registered in Windows (roblox-studio-auth:, battlenet:…) open it on Linux too.

    A login in the browser hands the result back to the program with such a link; without a handler the browser
    does nothing and the program waits in vain (Roblox Studio, 2026-10-29). The hidden entry passes the link to
    sloth-exe --open-url, which starts the registered command in the program's environment.
    -> the schemes now handled
    """
    from . import winreg

    schemes = sorted(s for s, command in winreg.url_protocols(app.prefix).items() if _own_command(app, command))
    path = url_handler_path(app)
    old = _read(path)
    old_schemes = sorted(m[len("x-scheme-handler/"):] for m in (old.get("MimeType", "") if old else "").split(";") if m)
    if schemes == old_schemes:
        return schemes
    if not schemes:
        try:
            path.unlink()
        except OSError:
            pass
        _update_database()
        return schemes
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(shlex.quote(a) for a in ["sloth-exe", "--open-url", app.id]) + " %u"
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={app.name}\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
        f"MimeType={''.join(f'x-scheme-handler/{s};' for s in schemes)}\n"
        f"X-Sloth-Program={app.id}\n",
        encoding="utf-8")
    _update_database()
    for scheme in schemes:
        try:
            subprocess.run(["xdg-mime", "default", path.name, f"x-scheme-handler/{scheme}"],
                           capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("xdg-mime %s: %s", scheme, e)
    log.info("link types of %s: %s", app.id, ", ".join(schemes))
    return schemes


def _own_command(app, command):
    """Whether the command starts a program in the environment (not Wine's own, e.g. winebrowser)."""
    from . import detect, winreg

    exe, _args = winreg.split_command(command, "")
    host = app.windows_to_host(exe or "")
    if host is None or not host.is_file() or host.suffix.lower() != ".exe":
        return False
    return not detect.not_program(detect._rel(app, host))


def _update_database():
    try:
        subprocess.run(["update-desktop-database", str(APPS_DIR)], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def remove_entries(app):
    for e in entries(app):
        try:
            Path(e["desktop"]).unlink()
        except OSError:
            pass
    if url_handler_path(app).exists():
        url_handler_path(app).unlink(missing_ok=True)
        _update_database()


def set_category(app):
    """Rewrites the category (e.g. if it turned out on the first start that it is a game)."""
    for e in entries(app):
        path = Path(e["desktop"])
        try:
            text = path.read_text(encoding="utf-8")
            new = re.sub(r"(?m)^Categories=.*$", f"Categories={_categories(app)}X-SlothWindowsProgram;", text)
            if new != text:
                path.write_text(new, encoding="utf-8")
        except OSError as e:
            log.warning("category: %s", e)


def relink(app, old_prefix):
    """After moving the folder: the paths of the icons and of the start files outside the environment.

    The start files inside the Windows environment (relative) stay valid. If a relative path pointed outside the old
    environment (the old .exe handler wrote downloaded .exe files like that), it becomes a full path.
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
            log.warning("updating the entry: %s", err)
    icon = next((e["icon"] for e in entries(app) if e["icon"].startswith("/")), None)
    if icon:
        app.set_folder_icon(icon)
