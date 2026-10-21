"""Self-healing start: every Windows program finds the setting that works for it by itself.

There is no Proton setting that works for everything, so we remember per program (more precisely per .exe)
what worked. If a program exits quickly after starting, the next attempt uses another setting,
and the user only sees "Starting…". The order:
  1. what worked last time, but if a newer Proton came since, first with that (update); if that does not work,
     back to the old one, and that program stays on it (rollback after updates),
  2. the fixes for errors recognized from the log (diagnose.py), with the same setting,
  3. a sequence of attempts: default, without fsync, WineD3D (without Vulkan), GE-Proton, an older Proton.
Before a Proton switch a snapshot of the program's folder is taken (a reflink copy: seconds, almost
zero space), and if the attempt fails, it is restored; so a bad attempt never breaks anything.

Data: in the program's data (sloth_common.apps, .sloth/app.json), under "launch" per .exe (a shared
environment can have several .exe files).
"""
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sloth_common.apps import library

DATA_HOME = library.DATA_HOME
COMPAT_DIRS = [DATA_HOME / "Steam/compatibilitytools.d", DATA_HOME / "umu/compatibilitytools"]
UMU_LINE, GE_LINE = "UMU-Proton", "GE-Proton"
GE_DOWNLOAD = "GE-Proton"  # seeing this name, umu downloads the latest GE-Proton

# Settings for the attempts: environment variables
PROFILES = {
    "default": {},
    "nofsync": {"PROTON_NO_FSYNC": "1", "PROTON_NO_ESYNC": "1"},
    "wined3d": {"PROTON_USE_WINED3D": "1"},
}
MAX_ATTEMPTS = 4  # at most this many attempts within one start (then a clear error message)


# --- Proton versions --------------------------------------------------------------------------------

def _version_key(name):
    return [int(n) for n in re.findall(r"\d+", name)]


def installed_protons(line=None):
    """The installed Protons {name: folder}, the newest first (line: "UMU-Proton" / "GE-Proton")."""
    found = {}
    for base in COMPAT_DIRS:
        if not base.is_dir():
            continue
        for d in base.iterdir():
            if (d / "proton").is_file() and d.name.startswith((UMU_LINE, GE_LINE)):
                if line is None or d.name.startswith(line):
                    found.setdefault(d.name, d)
    return dict(sorted(found.items(), key=lambda kv: _version_key(kv[0]), reverse=True))


def newest(line=UMU_LINE):
    return next(iter(installed_protons(line)), None)


def protonpath(name):
    """The value of PROTONPATH: an installed version's folder, or a name to download (GE-Proton); None = umu decides."""
    if not name:
        return None
    if name == GE_DOWNLOAD:
        return GE_DOWNLOAD
    d = installed_protons().get(name)
    return str(d) if d else None


# --- Per-program data -------------------------------------------------------------------------

def _key(program, exe):
    try:
        return os.path.relpath(exe, program.prefix)
    except ValueError:
        return str(exe)


def record(program, exe):
    return program.meta.get("launch", {}).get(_key(program, exe), {})


def save_record(program, exe, rec):
    launch = program.meta.get("launch", {})
    launch[_key(program, exe)] = rec
    program.save_meta(launch=launch)


# --- Snapshot ------------------------------------------------------------------------------------

def can_snapshot(program):
    """Whether the file system supports reflink copies (Btrfs, XFS); otherwise copying would take too much space."""
    program.data.mkdir(parents=True, exist_ok=True)
    src = program.data / f".reflink-{uuid.uuid4().hex}"
    dst = src.with_suffix(".copy")
    try:
        src.write_bytes(b"x")
        return subprocess.run(["cp", "--reflink=always", str(src), str(dst)],
                              stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        src.unlink(missing_ok=True)
        dst.unlink(missing_ok=True)


def take_snapshot(program):
    dest = program.snapshot
    drop_snapshot(program, wait=True)
    try:
        return subprocess.run(["cp", "-a", "--reflink=always", str(program.prefix), str(dest)],
                              stderr=subprocess.DEVNULL, timeout=600).returncode == 0
    except (OSError, subprocess.SubprocessError):
        drop_snapshot(program, wait=True)
        return False


def restore_snapshot(program):
    snap = program.snapshot
    if not snap.is_dir():
        return False
    trash = program.data / f".regi-{uuid.uuid4().hex}"
    program.prefix.rename(trash)
    snap.rename(program.prefix)
    subprocess.Popen(["rm", "-rf", str(trash)], start_new_session=True)
    return True


def drop_snapshot(program, wait=False):
    snap = program.snapshot
    if not snap.exists():
        return
    if wait:
        shutil.rmtree(snap, ignore_errors=True)
    else:
        trash = program.data / f".regi-{uuid.uuid4().hex}"
        snap.rename(trash)
        subprocess.Popen(["rm", "-rf", str(trash)], start_new_session=True)


# --- Plan: in which order to try ---------------------------------------------------------

@dataclass
class Attempt:
    proton: str | None   # an installed version's name, GE_DOWNLOAD, or None (umu decides)
    profile: str = "default"
    fixes: list = field(default_factory=list)

    @property
    def key(self):
        return f"{self.proton or 'auto'}|{self.profile}"

    def env(self):
        out = dict(PROFILES.get(self.profile, {}))
        for kind, value in self.fixes:
            if kind == "env":
                out[value] = "1"
        path = protonpath(self.proton)
        if path:
            out["PROTONPATH"] = path
        return out

    def args(self):
        return [value for kind, value in self.fixes if kind == "args"]

    def verbs(self):
        return [value for kind, value in self.fixes if kind == "verb"]


def plan(program, exe, suggest=None):
    """The order of attempts for this start.

    suggest: the shared knowledge's suggestion (community.suggestion): (Proton line, profile, fixes) or None.
    """
    rec = record(program, exe)
    fixes = [tuple(f) for f in rec.get("fixes", [])]
    failed = set(rec.get("failed", []))
    current = newest(UMU_LINE)
    older = list(installed_protons(UMU_LINE))[1:2]
    out = []

    def add(proton, profile):
        a = Attempt(proton, profile, fixes)
        if a.key not in failed and all(a.key != b.key for b in out):
            out.append(a)

    good = rec.get("good")
    if good:
        installed = good["proton"] in installed_protons() or good["proton"] == "auto"
        # A newer Proton came: first with that, and if it does not work, back to the version that worked
        if current and good["proton"].startswith(UMU_LINE) and good["proton"] != current:
            add(current, good["profile"])
        if installed:
            out.append(Attempt(None if good["proton"] == "auto" else good["proton"], good["profile"], fixes))
        else:
            add(current, good["profile"])
    if suggest and not good:
        # This worked on other machines: it is the first attempt (together with our own recognized fixes)
        line, profile, extra = suggest
        proton = current if line == UMU_LINE else (newest(GE_LINE) or GE_DOWNLOAD)
        a = Attempt(proton, profile, fixes + [f for f in extra if f not in fixes])
        if a.key not in failed:
            out.append(a)
    add(current, "default")
    add(current, "nofsync")
    add(current, "wined3d")
    add(GE_DOWNLOAD, "default")
    for name in older:
        add(name, "default")
    return out[:MAX_ATTEMPTS]


def prefix_proton(program):
    return program.meta.get("prefix_proton")


def resolved_name(attempt):
    """The name of the version actually used, after the run (with GE-Proton it turns out after the download)."""
    if attempt.proton == GE_DOWNLOAD:
        return newest(GE_LINE) or GE_DOWNLOAD
    return attempt.proton or newest(UMU_LINE) or "auto"


def needs_snapshot(program, attempt):
    """Proton switch: if it fails, we must be able to go back to the old state."""
    current = prefix_proton(program)
    return bool(current) and resolved_name(attempt) != current


def allowed_without_snapshot(program, attempt):
    """Without a snapshot only stepping forward is safe (Proton updates an older folder, not backwards)."""
    return not needs_snapshot(program, attempt) or attempt.proton == newest(UMU_LINE)


# --- Maintenance ------------------------------------------------------------------------------------

def _in_use(path):
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if str(path).encode() in (proc / "cmdline").read_bytes():
                return True
        except OSError:
            continue
    return False


def prune_protons():
    """Deletes old Protons: keeps the latest UMU- and GE-Proton, one spare, and whatever a program uses."""
    keep = {newest(UMU_LINE), newest(GE_LINE)}
    keep |= set(list(installed_protons(UMU_LINE))[:2])
    for app in library.all_apps():
        meta = app.meta
        keep.add(meta.get("prefix_proton"))
        for rec in meta.get("launch", {}).values():
            keep.add((rec.get("good") or {}).get("proton"))
    removed = []
    for name, path in installed_protons().items():
        if name in keep or _in_use(path) or path.parent != COMPAT_DIRS[0]:
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(name)
    return removed
