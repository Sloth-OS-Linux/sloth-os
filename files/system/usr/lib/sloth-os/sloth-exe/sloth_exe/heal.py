"""Önjavító indítás: minden Windows-program találja meg magától a neki működő beállítást.

Egy mindenre jó Proton-beállítás nincs, ezért programonként (pontosabban .exe-nként) megjegyezzük,
mi működött. Ha egy program indítás után gyorsan kilép, a következő próbálkozás más beállítással megy,
a felhasználó ebből csak annyit lát, hogy „Indítás…”. A sorrend:
  1. ami legutóbb működött, de ha azóta újabb Proton jött, előbb azzal (frissítés); ha az nem megy,
     vissza a régihez, és annál a programnál az marad (visszaállás frissítés után),
  2. a naplóból felismert hibák javításai (diagnose.py), ugyanazzal a beállítással,
  3. próbálkozási sor: alap, fsync nélkül, WineD3D (Vulkan nélkül), GE-Proton, egy régebbi Proton.
Proton-váltás előtt pillanatkép készül a program mappájáról (reflink másolat: másodpercek, szinte
nulla hely), és ha a próba nem sikerül, visszaáll; így egy rossz próba semmit nem ront el.

Adatok: a program meta.json-jában, "launch" alatt .exe-nként (a közös mappában több .exe is lehet).
"""
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import programs

DATA_HOME = programs.DATA_HOME
COMPAT_DIRS = [DATA_HOME / "Steam/compatibilitytools.d", DATA_HOME / "umu/compatibilitytools"]
UMU_LINE, GE_LINE = "UMU-Proton", "GE-Proton"
GE_DOWNLOAD = "GE-Proton"  # az umu ezt a nevet látva letölti a legfrissebb GE-Protont

# Próbálkozási beállítások: környezeti változók
PROFILES = {
    "default": {},
    "nofsync": {"PROTON_NO_FSYNC": "1", "PROTON_NO_ESYNC": "1"},
    "wined3d": {"PROTON_USE_WINED3D": "1"},
}
MAX_ATTEMPTS = 4  # egy indításon belül legfeljebb ennyi próba (utána érthető hibaüzenet)
SNAPSHOT_NAME = "pillanatkep"


# --- Proton-verziók --------------------------------------------------------------------------------

def _version_key(name):
    return [int(n) for n in re.findall(r"\d+", name)]


def installed_protons(line=None):
    """A telepített Protonok {név: mappa}, a legújabb elöl (line: "UMU-Proton" / "GE-Proton")."""
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
    """A PROTONPATH értéke: telepített verzió mappája, vagy letöltendő név (GE-Proton); None = az umu dönt."""
    if not name:
        return None
    if name == GE_DOWNLOAD:
        return GE_DOWNLOAD
    d = installed_protons().get(name)
    return str(d) if d else None


# --- Programonkénti adatok -------------------------------------------------------------------------

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


# --- Pillanatkép ------------------------------------------------------------------------------------

def can_snapshot(program):
    """Támogatja-e a fájlrendszer a reflink másolatot (Btrfs, XFS); különben a másolás túl sok hely lenne."""
    program.dir.mkdir(parents=True, exist_ok=True)
    src = program.dir / f".reflink-{uuid.uuid4().hex}"
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
    dest = program.dir / SNAPSHOT_NAME
    drop_snapshot(program, wait=True)
    try:
        return subprocess.run(["cp", "-a", "--reflink=always", str(program.prefix), str(dest)],
                              stderr=subprocess.DEVNULL, timeout=600).returncode == 0
    except (OSError, subprocess.SubprocessError):
        drop_snapshot(program, wait=True)
        return False


def restore_snapshot(program):
    snap = program.dir / SNAPSHOT_NAME
    if not snap.is_dir():
        return False
    trash = program.dir / f".regi-{uuid.uuid4().hex}"
    program.prefix.rename(trash)
    snap.rename(program.prefix)
    subprocess.Popen(["rm", "-rf", str(trash)], start_new_session=True)
    return True


def drop_snapshot(program, wait=False):
    snap = program.dir / SNAPSHOT_NAME
    if not snap.exists():
        return
    if wait:
        shutil.rmtree(snap, ignore_errors=True)
    else:
        trash = program.dir / f".regi-{uuid.uuid4().hex}"
        snap.rename(trash)
        subprocess.Popen(["rm", "-rf", str(trash)], start_new_session=True)


# --- Terv: milyen sorrendben próbálkozzunk ---------------------------------------------------------

@dataclass
class Attempt:
    proton: str | None   # telepített verzió neve, GE_DOWNLOAD, vagy None (az umu dönt)
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
    """A próbálkozások sorrendje erre az indításra.

    suggest: a közös tudás javaslata (community.suggestion): (Proton-vonal, profil, javítások) vagy None.
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
        # Újabb Proton jött: előbb azzal, és ha nem megy, vissza a bevált verzióhoz
        if current and good["proton"].startswith(UMU_LINE) and good["proton"] != current:
            add(current, good["profile"])
        if installed:
            out.append(Attempt(None if good["proton"] == "auto" else good["proton"], good["profile"], fixes))
        else:
            add(current, good["profile"])
    if suggest and not good:
        # Más gépeken ez vált be: ez az első próba (a saját felismert javításokkal együtt)
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
    """A ténylegesen használt verzió neve a futás után (a GE-Protonnál letöltés után derül ki)."""
    if attempt.proton == GE_DOWNLOAD:
        return newest(GE_LINE) or GE_DOWNLOAD
    return attempt.proton or newest(UMU_LINE) or "auto"


def needs_snapshot(program, attempt):
    """Proton-váltás: ha nem sikerül, vissza kell tudni állni a régi állapotra."""
    current = prefix_proton(program)
    return bool(current) and resolved_name(attempt) != current


def allowed_without_snapshot(program, attempt):
    """Pillanatkép nélkül csak az előre lépés biztonságos (a Proton a régebbi mappát frissíti, visszafelé nem)."""
    return not needs_snapshot(program, attempt) or attempt.proton == newest(UMU_LINE)


# A Wine saját háttérfolyamatai: a program kilépése után még pár másodpercig élhetnek
_INFRA = {"services.exe", "winedevice.exe", "plugplay.exe", "explorer.exe", "rpcss.exe", "svchost.exe",
          "tabtip.exe", "conhost.exe", "start.exe", "steam.exe", "wineboot.exe", "rundll32.exe", "winemenubuilder.exe"}


def _windows_exe(proc):
    """A folyamat Windows-programjának neve (a Wine alatt az első paraméter a .exe útvonala), vagy None."""
    argv0 = (proc / "cmdline").read_bytes().split(b"\0", 1)[0].decode("utf-8", "replace")
    name = re.split(r"[\\/]", argv0)[-1].lower()
    return name if name.endswith(".exe") else None


def prefix_busy(program):
    """Fut-e még maga a program a mappájában (pl. az indító kilépett, de a kliens tovább fut)."""
    marker = b"WINEPREFIX=" + str(program.prefix).encode() + b"\0"
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if marker in (proc / "environ").read_bytes():
                name = _windows_exe(proc)
                if name and name not in _INFRA:
                    return True
        except OSError:
            continue
    return False


# --- Karbantartás ------------------------------------------------------------------------------------

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
    """A régi Protonok törlése: marad a legújabb UMU- és GE-Proton, egy tartalék, és amit egy program használ."""
    keep = {newest(UMU_LINE), newest(GE_LINE)}
    keep |= set(list(installed_protons(UMU_LINE))[:2])
    if programs.ROOT.is_dir():
        for d in programs.ROOT.iterdir():
            meta = programs.Program(d.name).meta
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
