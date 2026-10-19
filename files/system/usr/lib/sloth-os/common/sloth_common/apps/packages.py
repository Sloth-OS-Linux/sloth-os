"""Linuxos (és Mac-es) programcsomagok: mi ez a fájl, és hogyan kerül a gépre.

  AppImage   a programok közé kerül (~/Applications/<név>/), futtathatóra állítva, a Start menüben a saját
             nevével és ikonjával. Futtatásához a FUSE 2 kell (fuse-libs, recipes/tools.yml).
  .deb       Fedorán közvetlenül nem telepíthető: egy Ubuntu-dobozba (distrobox) kerül, az appjai a Start
             menüben natívként jelennek meg; a „doboz” szó a felületen nem látszik.
  .rpm       Atomic rendszeren nem rétegezzük (az csak a haladó beállításokban): egy Fedora-dobozba kerül.
  Mac        (.dmg, .pkg, .app…) Linuxon nem futtatható: érthető üzenet, és a Discoverben keresés a
             Linuxos változatra.
A felismerés a fájl tartalma alapján megy (nem csak a kiterjesztés szerint).
"""
import configparser
import logging
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from . import library, menu

log = logging.getLogger("sloth-os.apps")

MAC_EXT = {".dmg", ".pkg", ".mpkg", ".app", ".xip", ".sparseimage", ".sparsebundle", ".cdr", ".smi", ".dc42",
           ".ipa"}
MAC_SCRIPT_EXT = {".command", ".tool"}

# Dobozok a Linuxos csomagokhoz: (doboz neve, image, telepítés, csomagnév kiolvasása, eltávolítás)
BOXES = {
    "deb": ("sloth-ubuntu", "docker.io/library/ubuntu:24.04",
            'sudo -n apt-get update && sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y "$PKG"',
            'dpkg-deb -f "$PKG" Package',
            'sudo -n DEBIAN_FRONTEND=noninteractive apt-get remove -y "$NAME"'),
    "rpm": ("sloth-fedora", "registry.fedoraproject.org/fedora-toolbox:44",
            'sudo -n dnf install -y "$PKG"',
            'rpm -qp --qf "%{NAME}" "$PKG"',
            'sudo -n dnf remove -y "$NAME"'),
}


def kind_of(path):
    """"appimage" | "deb" | "rpm" | "mac" | "mac-script" | None (a fájl tartalma, és ha kell, a neve alapján)."""
    p = Path(path)
    ext = "".join(p.suffixes[-2:]).lower() if p.name.lower().endswith(".app.zip") else p.suffix.lower()
    try:
        with open(p, "rb") as f:
            head = f.read(64)
            f.seek(0, 2)
            size = f.tell()
            if size > 512:
                f.seek(-512, 2)
                tail = f.read(512)
            else:
                tail = b""
    except OSError:
        head, tail = b"", b""
    if head[:4] == b"\x7fELF" and head[8:11] in (b"AI\x01", b"AI\x02"):
        return "appimage"
    if head.startswith(b"!<arch>\ndebian-binary"):
        return "deb"
    if head[:4] == b"\xed\xab\xee\xdb":
        return "rpm"
    if head[:4] == b"xar!" or tail[:4] == b"koly":  # .pkg (xar), .dmg (UDIF lábléc)
        return "mac"
    if ext == ".appimage":
        return "appimage"
    if ext in (".deb", ".rpm"):
        return ext[1:]
    if ext in MAC_EXT or ext == ".app.zip" or p.is_dir() and ext == ".app":
        return "mac"
    if ext in MAC_SCRIPT_EXT:
        return "mac-script"
    return None


def display_name(path):
    """Krita-5.2.6-x86_64.AppImage -> "Krita"; signal-desktop_7.1_amd64.deb -> "Signal Desktop"."""
    stem = Path(path).name
    stem = re.sub(r"(?i)\.(appimage|deb|rpm|dmg|pkg|app\.zip|app)$", "", stem)
    stem = re.split(r"[-_ ]v?\d", stem, maxsplit=1)[0]
    stem = re.sub(r"(?i)[-_.](x86_64|amd64|aarch64|arm64|linux|setup)$", "", stem)
    s = re.sub(r"[-_]+", " ", stem).strip()
    return (s.title() if s.islower() else s) or Path(path).stem


# --- AppImage -----------------------------------------------------------------------------------------

def _desktop_info(text):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read_string(text)
        e = cp["Desktop Entry"]
        return {"name": e.get("Name", ""), "icon": e.get("Icon", ""), "categories": e.get("Categories", "")}
    except (configparser.Error, KeyError):
        return {}


def appimage_info(appimage, dest_icon):
    """Név, ikon és kategóriák az AppImage-ből (a saját kicsomagolójával, ablak nélkül)."""
    info = {}
    with tempfile.TemporaryDirectory() as tmp:
        for pattern in ("*.desktop", ".DirIcon"):
            try:
                subprocess.run([str(appimage), "--appimage-extract", pattern], cwd=tmp, timeout=60,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError) as e:
                log.warning("AppImage kicsomagolása: %s", e)
                return info
        root = Path(tmp) / "squashfs-root"
        desktops = sorted(root.glob("*.desktop"))
        if desktops:
            info = _desktop_info(desktops[0].read_text(encoding="utf-8", errors="replace"))
        icon = root / ".DirIcon"
        if icon.is_symlink():  # a .DirIcon többnyire hivatkozás a valódi ikonra
            target = icon.readlink()
            subprocess.run([str(appimage), "--appimage-extract", str(target)], cwd=tmp, timeout=60,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            icon = root / target
        if icon.is_file():
            data = icon.read_bytes()
            dest = Path(dest_icon).with_suffix(".svg" if b"<svg" in data[:512] else ".png")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            info["icon_path"] = str(dest)
    return info


def install_appimage(src, name=None):
    """Az AppImage a programok közé (másolat; Btrfs-en reflink, így nem foglal kétszer helyet).

    -> az új App, vagy None (ha a hely nem jó, vagy a másolás nem sikerült)."""
    src = Path(src)
    if not library.supported_location(library.default_library()):
        return None
    app = library.create(name or display_name(src), kind="appimage", source={"from": "file", "file": str(src)})
    dest = app.dir / src.name
    try:
        subprocess.run(["cp", "--reflink=auto", str(src), str(dest)], check=True, capture_output=True, timeout=600)
        dest.chmod(0o755)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("AppImage másolása: %s", e)
        library.remove(app)
        return None
    info = appimage_info(dest, app.icons / "appimage")
    if info.get("name") and info["name"] != app.name:
        app.save_meta(file=dest.name)
        app = library.rename(app, info["name"])
        dest = app.dir / dest.name
    app.save_meta(file=dest.name, categories=info.get("categories", ""))
    icon = info.get("icon_path")
    if icon:
        icon = str(app.icons / Path(icon).name)  # az átnevezés után is a program mappájában
    menu.add_command(app, app.name, ["sloth-exe", "--run", app.id], icon, info.get("categories"),
                     args_placeholder="%U")
    app.set_folder_icon(icon)
    return app


def appimage_path(app):
    f = app.meta.get("file")
    return app.dir / f if f else None


# --- .deb / .rpm dobozban ----------------------------------------------------------------------------

def box_path(path):
    """A fájl útja a dobozon belül: a saját mappa ugyanott látszik, a többi a /run/host alatt."""
    p = Path(path).resolve()
    try:
        p.relative_to(Path.home().resolve())
        return str(p)
    except ValueError:
        return f"/run/host{p}"


def box_steps(kind, path, box_exists):
    """A dobozos telepítés lépései: [(állapot kulcsa, parancs)]. Az utolsó lépés kiírja:
       SLOTH-NAME:<csomagnév> és soronként SLOTH-APP:<desktop azonosító>|<név> (a Start menübe került appok)."""
    box, image, install, pkg_name, _remove = BOXES[kind]
    steps = []
    if not box_exists:
        steps.append(("box.create", ["distrobox", "create", "--yes", "--name", box, "--image", image]))
        steps.append(("box.first_start", ["distrobox", "enter", box, "--", "true"]))
    script = (
        f'PKG={shlex.quote(box_path(path))}; '
        'before=$(ls /usr/share/applications 2>/dev/null); '
        f'{install} || exit 1; '
        f'echo "SLOTH-NAME:$({pkg_name})"; '
        'for f in /usr/share/applications/*.desktop; do '
        '  b=$(basename "$f"); echo "$before" | grep -qxF "$b" && continue; '
        '  grep -q "^NoDisplay=true" "$f" && continue; '
        '  n=$(grep -m1 "^Name=" "$f" | cut -d= -f2-); id="${b%.desktop}"; '
        '  distrobox-export --app "$id" >/dev/null 2>&1 && echo "SLOTH-APP:$id|$n"; '
        'done')
    steps.append(("box.install", ["distrobox", "enter", box, "--", "sh", "-c", script]))
    return steps


def parse_box_output(lines):
    name, apps = "", []
    for line in lines:
        if line.startswith("SLOTH-NAME:"):
            name = line[11:].strip()
        elif line.startswith("SLOTH-APP:") and "|" in line:
            app_id, label = line[10:].split("|", 1)
            apps.append({"id": app_id.strip(), "name": label.strip() or app_id.strip()})
    return name, apps


def box_exists(kind):
    box = BOXES[kind][0]
    try:
        r = subprocess.run(["podman", "container", "exists", box], capture_output=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def record_box_install(kind, path, package, apps):
    """A dobozba telepített csomag a programok közé (rejtett adat; a Start menü bejegyzéseit a distrobox írja)."""
    name = apps[0]["name"] if len(apps) == 1 else (package or display_name(path))
    return library.create(name, kind="box", box={"kind": kind, "box": BOXES[kind][0], "package": package,
                                                 "apps": apps, "file": str(path)})


def box_uninstall(app):
    """A doboz appjai ki a Start menüből, a csomag ki a dobozból. -> True, ha sikerült."""
    info = app.meta.get("box") or {}
    kind = info.get("kind")
    if kind not in BOXES or not info.get("package"):
        return False
    box, _image, _install, _name, remove = BOXES[kind]
    unexport = "; ".join(f"distrobox-export --app {shlex.quote(a['id'])} --delete >/dev/null 2>&1"
                         for a in info.get("apps", []))
    script = f'NAME={shlex.quote(info["package"])}; {unexport + "; " if unexport else ""}{remove}'
    try:
        r = subprocess.run(["distrobox", "enter", box, "--", "sh", "-c", script], capture_output=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("eltávolítás a dobozból: %s", e)
        return False
    return r.returncode == 0


def box_desktop_files(app):
    """A distrobox által a Start menübe tett bejegyzések (<doboz>-<app>.desktop)."""
    info = app.meta.get("box") or {}
    return [menu.APPS_DIR / f"{info.get('box')}-{a['id']}.desktop" for a in info.get("apps", [])]


def box_launch_command(app):
    """A dobozba telepített (első) app indítása a Start menü bejegyzésével."""
    desktop = next((d for d in box_desktop_files(app) if d.is_file()), None)
    return ["kioclient", "exec", str(desktop)] if desktop else None
