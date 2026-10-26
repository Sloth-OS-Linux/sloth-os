"""Disc images (.iso): opening them with a double-click, like on Windows.

The image is attached read-only through UDisks (no password for the signed-in user) and mounted where Dolphin
shows it (/run/media/<user>/<name>, with an eject button). The loop device clears itself when the image is
ejected (autoclear), and the images still open are ejected at sign-out (/usr/libexec/sloth-os/disc-images).
If it has an installer (autorun.inf's open=, or a setup.exe / install.exe at the top), the .exe handler offers
it; the user can make the choice permanent (~/.config/sloth-os/disc-images.json: {"action": "install" |
"folder"}).
"""
import configparser
import json
import os
import re
import subprocess
import time
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "disc-images.json"
ISO_EXT = {".iso", ".img"}
INSTALLERS = ("setup.exe", "install.exe", "autorun.exe")


def is_disc_image(path):
    """An .iso file, or an .img with an ISO 9660 / UDF signature (CD001 / NSR0x at 32 KiB)."""
    p = Path(path)
    if p.suffix.lower() == ".iso":
        return True
    if p.suffix.lower() not in ISO_EXT:
        return False
    try:
        with open(p, "rb") as f:
            f.seek(32769)
            return f.read(5) in (b"CD001", b"BEA01")
    except OSError:
        return False


def _udisks(*args):
    r = subprocess.run(["udisksctl", *args, "--no-user-interaction"], capture_output=True, text=True, timeout=30)
    return r.stdout + r.stderr


def _attached(path):
    """The loop device the image is already attached to (opened twice), or ""."""
    try:
        out = subprocess.run(["losetup", "--noheadings", "--output", "NAME", "--associated", str(path)],
                             capture_output=True, text=True, timeout=10).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return ""
    return out[0] if out else ""


def _mounted_at(text):
    m = re.search(r"(?:Mounted \S+ at|already mounted at) [`']?(/[^'`\n]+?)[`']?\.?\s*$", text, re.M)
    return Path(m.group(1)) if m else None


def _autoclear(dev):
    """The loop device goes away by itself once the image is ejected. Only set after mounting: before that, the
    first close (udev probing the new device) would already clear it."""
    obj = "/org/freedesktop/UDisks2/block_devices/" + Path(dev).name
    try:
        subprocess.run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UDisks2", "--object-path", obj,
                        "--method", "org.freedesktop.UDisks2.Loop.SetAutoclear", "true",
                        "{'auth.no_user_interaction': <true>}"],
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def mount(path):
    """Attaches and mounts the image; returns the folder, or None if it could not be opened."""
    path = Path(path).resolve()
    dev = _attached(path)
    if not dev:
        m = re.search(r"as (/dev/loop\d+)", _udisks("loop-setup", "--read-only", "-f", str(path)))
        if not m:
            return None
        dev = m.group(1)
    # UDisks needs a moment to recognize the file system; a hybrid image has it on a partition (loopNp1)
    for _ in range(20):
        for candidate in (dev, f"{dev}p1"):
            if not Path(candidate).exists():
                continue
            where = _mounted_at(_udisks("mount", "-b", candidate))
            if where and where.is_dir():
                _autoclear(dev)
                return where
        time.sleep(0.5)
    return None


def _find(folder, name):
    """A file in the folder by name, ignoring upper/lower case (Windows discs mix them)."""
    want = name.lower().replace("\\", "/").strip("/")
    current = Path(folder)
    for part in want.split("/"):
        try:
            current = next(c for c in current.iterdir() if c.name.lower() == part)
        except (OSError, StopIteration):
            return None
    return current if current.is_file() else None


def installer_on(folder):
    """The installer on the disc: autorun.inf's open= (without its arguments), or a setup.exe at the top."""
    inf = _find(folder, "autorun.inf")
    if inf:
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            cp.read_string(inf.read_text(encoding="utf-8", errors="replace"))
            sections = {s.lower(): s for s in cp.sections()}
            if "autorun" in sections:
                opener = dict((k.lower(), v) for k, v in cp.items(sections["autorun"])).get("open", "")
                exe = re.match(r'\s*"?([^"]+?\.(?:exe|msi))', opener, re.I)
                found = exe and _find(folder, exe.group(1))
                if found:
                    return found
        except (configparser.Error, OSError):
            pass
    for name in INSTALLERS:
        found = _find(folder, name)
        if found:
            return found
    return None


def preference():
    """"install", "folder" or "" (ask)."""
    try:
        action = json.loads(CONFIG.read_text(encoding="utf-8")).get("action", "")
    except (OSError, ValueError):
        return ""
    return action if action in ("install", "folder") else ""


def remember(action):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"action": action}) + "\n", encoding="utf-8")
