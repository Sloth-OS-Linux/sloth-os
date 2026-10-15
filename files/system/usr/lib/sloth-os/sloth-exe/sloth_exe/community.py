"""Közös tudás: ami más Sloth OS-es gépeken bevált, az nálunk is elsőre induljon.

Olvasás (mindig): a sloth-windows-prepare letölti az összesítést a GitHubról (KNOWLEDGE_URL); ez egy
statikus fájl, a letöltéséből semmi nem derül ki rólunk.
Megosztás (csak ha a felhasználó bekapcsolta a Sloth Központban, alapból ki): a bevált vagy sikertelen
beállítás névtelen jelentése. A program nevét nem küldjük, csak egy ujjlenyomatát (program_key), a gép
azonosítója egy véletlen szám. A jelentések sorba kerülnek, és a sloth-windows-prepare küldi el őket,
így az indítás soha nem vár a hálózatra. A szolgáltatás: services/knowledge/ (a repóban).
"""
import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from sloth_common import sharing

from . import diagnose, heal, identify

log = logging.getLogger("sloth-exe.community")

KNOWLEDGE_URL = "https://raw.githubusercontent.com/bathorizsolt/sloth-os-knowledge/main/knowledge.json"
REPORT_URL = "https://sloth-os-knowledge.slothos.workers.dev/v1/report"

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "knowledge.json"
QUEUE = sharing.QUEUE
STATE = QUEUE.parent
MACHINE_ID = STATE / "community-id"
MAX_QUEUE = 500

# Amit elfogadunk a közös tudásból (a szolgáltatás is csak ezeket engedi; kétszeres védelem)
# Proton be/ki kapcsolók (mind "=1" értékkel): a ProtonDB-ből és a jelentésekből is csak ezek jöhetnek
ALLOWED_ENV = {"PROTON_USE_WINED3D", "PROTON_ENABLE_NVAPI", "PROTON_HIDE_NVIDIA_GPU",
               "PROTON_FORCE_LARGE_ADDRESS_AWARE", "PROTON_HEAP_DELAY_FREE", "PROTON_NO_D3D11", "PROTON_NO_D3D10",
               "PROTON_OLD_GL_STRING", "PROTON_NO_WRITE_WATCH"}
ALLOWED_FIXES = ({("verb", v) for v in set(diagnose.DLL_VERBS.values()) | {"dotnet48"}}
                 | {("env", e) for e in ALLOWED_ENV} | {("args", "--disable-gpu")})
_PCI_VENDORS = {"0x1002": "amd", "0x10de": "nvidia", "0x8086": "intel"}


def program_key(exe, names):
    """A program ujjlenyomata: a (felismert) név és a .exe neve, hash-elve. A nevet így senki nem látja."""
    name = identify.normalize(names[0]) if names else ""
    return hashlib.sha256(f"sloth-v1|{name}|{Path(exe).name.lower()}".encode()).hexdigest()


def gpu_vendor():
    """A videókártya gyártója; ha több van (pl. laptopban), a különálló (AMD / NVIDIA) számít."""
    found = set()
    for vendor in Path("/sys/class/drm").glob("card*/device/vendor"):
        try:
            found.add(_PCI_VENDORS.get(vendor.read_text().strip(), "other"))
        except OSError:
            continue
    for v in ("nvidia", "amd", "intel"):
        if v in found:
            return v
    return "other"


def _line(proton):
    for line in (heal.UMU_LINE, heal.GE_LINE):
        if proton and proton.startswith(line):
            return line
    return heal.UMU_LINE  # "auto": az umu alapértelmezése


def suggestion(key, gameid=None):
    """A közös tudás javaslata erre a programra és GPU-ra: (Proton-vonal, profil, javítások) vagy None.

    Előbb a Sloth OS-es gépek jelentései (program ujjlenyomata szerint), ha ott nincs, a ProtonDB-ből
    összesített adatok (felismert játéknál, Steam AppID szerint; előbb erre a GPU-gyártóra, aztán bármire).
    """
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    gpu = gpu_vendor()
    candidates = [((data.get("programs") or {}).get(key) or {}).get(gpu)]
    if gameid:
        game = (data.get("games") or {}).get(gameid) or {}
        candidates += [game.get(gpu), game.get("any")]
    entry = next((c for c in candidates if isinstance(c, dict)), None)
    if not entry:
        return None
    line, profile = entry.get("line"), entry.get("profile")
    fixes = [tuple(f) for f in entry.get("fixes", []) if isinstance(f, list) and tuple(f) in ALLOWED_FIXES]
    if line not in (heal.UMU_LINE, heal.GE_LINE) or profile not in heal.PROFILES:
        return None
    return line, profile, fixes


def _machine_id():
    try:
        value = MACHINE_ID.read_text().strip()
        uuid.UUID(value)
        return value
    except (OSError, ValueError):
        value = str(uuid.uuid4())
        STATE.mkdir(parents=True, exist_ok=True)
        MACHINE_ID.write_text(value)
        return value


def queue_report(key, attempt, outcome):
    """Jelentés a sorba (csak ha a megosztás be van kapcsolva)."""
    if not key or not sharing.enabled():
        return
    fixes = sorted([list(f) for f in attempt.fixes if tuple(f) in ALLOWED_FIXES])
    item = {"machine": _machine_id(), "program": key, "gpu": gpu_vendor(),
            "line": _line(heal.resolved_name(attempt)), "profile": attempt.profile, "fixes": fixes,
            "outcome": outcome}
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        lines = QUEUE.read_text(encoding="utf-8").splitlines() if QUEUE.exists() else []
        lines = (lines + [json.dumps(item)])[-MAX_QUEUE:]
        QUEUE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        log.warning("közös tudás (sor): %s", e)


def send_queue():
    """A sorban álló jelentések elküldése (a sloth-windows-prepare hívja). -> elküldött darabszám"""
    if not sharing.enabled() or not QUEUE.exists():
        return 0
    items = [json.loads(line) for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    sent = 0
    for i in range(0, len(items), 50):
        batch = items[i:i + 50]
        req = urllib.request.Request(REPORT_URL, data=json.dumps(batch).encode(), method="POST",
                                     headers={"content-type": "application/json", "user-agent": "SlothOS/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20):
                sent += len(batch)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                sent += len(batch)  # hibás jelentés: újraküldve sem lesz jó, eldobjuk
                continue
            break
        except OSError:
            break
    rest = items[sent:]
    if rest:
        QUEUE.write_text("".join(json.dumps(x) + "\n" for x in rest), encoding="utf-8")
    else:
        QUEUE.unlink(missing_ok=True)
    return sent
