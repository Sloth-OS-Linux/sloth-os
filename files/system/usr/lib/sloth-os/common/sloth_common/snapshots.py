"""Automatic backup of your own files: Btrfs snapshots of /var/home.

The saved states are under /var/home/.snapshots/<time> (read-only subvolumes, named in UTC
"2026-10-20_07-00-00"). The user can read them: the permissions in the snapshot are the old ones too, so everyone
only sees their own files. The work is done as root by /usr/libexec/sloth-os/home-snapshots (timer), the
setting is written by sloth-helper; this module only reads, so Sloth Center and Dolphin's "Previous versions"
window can use it without a password.

The big, re-downloadable folders (games, caches) are separate subvolumes, so they stay out of the backup
(EXCLUDED; home-snapshots layout makes them separate).
"""
import datetime
import json
import os
import random
import subprocess
from pathlib import Path

HOME_ROOT = Path("/var/home")
SNAP_DIR = HOME_ROOT / ".snapshots"
CONFIG = Path("/etc/sloth-os/snapshots.json")
NAME_FORMAT = "%Y-%m-%d_%H-%M-%S"
BTRFS_SUBVOL_INO = 256

# How long to keep, in days (Sloth Center → File backup)
KEEP_DAYS = {"2w": 14, "1m": 31, "3m": 92}
DEFAULTS = {"enabled": True, "keep": "1m"}

# Inside the home folder: these stay out of the backup (they can be downloaded again, and they change a lot).
# "*" is a folder name for any app (Flatpak: ~/.var/app/<app>/cache).
EXCLUDED = [
    ".cache",
    ".var/app/*/cache",
    ".local/share/Steam/steamapps",
    ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps",
    "Games",
]


def load_config():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    cfg = dict(DEFAULTS)
    if isinstance(data.get("enabled"), bool):
        cfg["enabled"] = data["enabled"]
    if data.get("keep") in KEEP_DAYS:
        cfg["keep"] = data["keep"]
    return cfg


def fs_type(path):
    r = subprocess.run(["stat", "-f", "-c", "%T", str(path)], capture_output=True, text=True)
    return r.stdout.strip()


def is_subvolume(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return st.st_ino == BTRFS_SUBVOL_INO and os.path.isdir(path) and not os.path.islink(path)


def state():
    """"ready" (works), "pending" (prepared at the next start) or "unsupported" (not Btrfs)."""
    if fs_type(HOME_ROOT) != "btrfs":
        return "unsupported"
    return "ready" if is_subvolume(HOME_ROOT) else "pending"


def parse_name(name):
    try:
        return datetime.datetime.strptime(name, NAME_FORMAT).replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def make_name(when):
    return when.astimezone(datetime.timezone.utc).strftime(NAME_FORMAT)


def list_snapshots():
    """[(name, time in UTC)], the newest first."""
    try:
        names = os.listdir(SNAP_DIR)
    except OSError:
        return []
    out = [(n, t) for n in names if (t := parse_name(n))]
    return sorted(out, key=lambda x: x[1], reverse=True)


def to_keep(snapshots, keep_days, now=None):
    """The names of the snapshots to keep: everything from the last 24 hours, then one a day (for at most 14 days),
    after that one a week, within the keep time. The newest always stays."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    keep, days, weeks = set(), set(), set()
    for i, (name, when) in enumerate(sorted(snapshots, key=lambda x: x[1], reverse=True)):
        age = now - when
        local = when.astimezone()
        if i == 0 or age < datetime.timedelta(days=1):
            keep.add(name)
        elif age > datetime.timedelta(days=keep_days):
            continue
        elif age < datetime.timedelta(days=min(14, keep_days)):
            if local.date() not in days:
                keep.add(name)
        elif local.isocalendar()[:2] not in weeks:
            keep.add(name)
        if name in keep:
            days.add(local.date())
            weeks.add(local.isocalendar()[:2])
    return keep


def locate(path):
    """Where a file is inside the backup: (path relative to /var/home, error).

    Error: "outside" (not under the home folders), "excluded" (left out of the backup)."""
    real = Path(os.path.realpath(path))
    try:
        rel = real.relative_to(HOME_ROOT)
    except ValueError:
        return None, "outside"
    if not rel.parts or rel.parts[0] == ".snapshots":
        return None, "outside"
    # whatever is in a separate subvolume (the excluded folders) is not in the backup
    current = HOME_ROOT
    for part in rel.parts:
        current = current / part
        if is_subvolume(current):
            return None, "excluded"
    return rel, ""


def versions_of(rel):
    """[(name, time, the file's path in the snapshot)] where the file / folder exists, the newest first."""
    out = []
    for name, when in list_snapshots():
        p = SNAP_DIR / name / rel
        if os.path.lexists(p):
            out.append((name, when, p))
    return out


def verify(folder, sample=300, read_bytes=65536, scan_limit=50000):
    """Reads a sample of the files of a saved state, to see that the backup can really be read back.

    -> (checked, [paths that could not be read]). Links are not followed; at most scan_limit files are looked at
    when choosing the sample, so a huge home folder does not take minutes."""
    files = []
    for root, dirs, names in os.walk(folder, onerror=lambda e: None):
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path) and not os.path.islink(path):
                files.append(path)
        if len(files) >= scan_limit:
            break
    unreadable, checked = [], 0
    for path in random.sample(files, min(sample, len(files))):
        try:
            with open(path, "rb") as f:
                f.read(read_bytes)
        except PermissionError:
            continue  # not the user's file to read (it was like this in the home folder too): not a backup fault
        except OSError:
            unreadable.append(path)
        checked += 1
    return checked, unreadable
