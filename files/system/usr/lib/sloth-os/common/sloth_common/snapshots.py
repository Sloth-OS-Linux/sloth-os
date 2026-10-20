"""A saját fájlok automatikus mentése: Btrfs-pillanatképek a /var/home-ról.

A mentett állapotok a /var/home/.snapshots/<időpont> alatt vannak (csak olvasható subvolume-ok, a nevük UTC-ben
"2026-10-20_07-00-00"). A felhasználó olvashatja őket: a jogosultságok a pillanatképben is a régiek, így mindenki
csak a saját fájljait látja. A munkát rootként a /usr/libexec/sloth-os/home-snapshots végzi (időzítő), a
beállítást a sloth-helper írja; ez a modul csak olvas, ezért a Sloth Központ és a Dolphin „Korábbi verziók”
ablaka jelszó nélkül használhatja.

A nagy, újra letölthető mappák (játékok, gyorsítótárak) külön subvolume-ok, ezért nem kerülnek a mentésbe
(EXCLUDED; a home-snapshots layout teszi őket külön).
"""
import datetime
import json
import os
import subprocess
from pathlib import Path

HOME_ROOT = Path("/var/home")
SNAP_DIR = HOME_ROOT / ".snapshots"
CONFIG = Path("/etc/sloth-os/snapshots.json")
NAME_FORMAT = "%Y-%m-%d_%H-%M-%S"
BTRFS_SUBVOL_INO = 256

# A megtartás ideje napokban (Sloth Központ → Fájlmentés)
KEEP_DAYS = {"2w": 14, "1m": 31, "3m": 92}
DEFAULTS = {"enabled": True, "keep": "1m"}

# A saját mappán belül: ezek nem kerülnek a mentésbe (újra letölthetők, és sokat változnak).
# A "*" egy mappanév bármelyik appnál (Flatpak: ~/.var/app/<app>/cache).
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
    """"ready" (megy), "pending" (a következő induláskor készül elő) vagy "unsupported" (nem Btrfs)."""
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
    """[(név, időpont UTC-ben)], a legújabb elöl."""
    try:
        names = os.listdir(SNAP_DIR)
    except OSError:
        return []
    out = [(n, t) for n in names if (t := parse_name(n))]
    return sorted(out, key=lambda x: x[1], reverse=True)


def to_keep(snapshots, keep_days, now=None):
    """A megtartandó pillanatképek nevei: az utolsó 24 óra mind, utána naponta egy (legfeljebb 14 napig),
    azután hetente egy, a megtartási időn belül. A legújabb mindig marad."""
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
    """Egy fájl helye a mentésen belül: (relatív út a /var/home-hoz képest, hiba).

    Hiba: "outside" (nem a saját mappák alatt van), "excluded" (kimarad a mentésből)."""
    real = Path(os.path.realpath(path))
    try:
        rel = real.relative_to(HOME_ROOT)
    except ValueError:
        return None, "outside"
    if not rel.parts or rel.parts[0] == ".snapshots":
        return None, "outside"
    # ami egy külön subvolume-ban van (a kihagyott mappák), az nincs a mentésben
    current = HOME_ROOT
    for part in rel.parts:
        current = current / part
        if is_subvolume(current):
            return None, "excluded"
    return rel, ""


def versions_of(rel):
    """[(név, időpont, a fájl útja a pillanatképben)], ahol a fájl / mappa megvan, a legújabb elöl."""
    out = []
    for name, when in list_snapshots():
        p = SNAP_DIR / name / rel
        if os.path.lexists(p):
            out.append((name, when, p))
    return out
