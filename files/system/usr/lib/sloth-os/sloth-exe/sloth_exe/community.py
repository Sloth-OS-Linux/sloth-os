"""Shared knowledge: what worked on other Sloth OS machines should start on the first try here too.

Reading (always): sloth-windows-prepare downloads the summary from GitHub (KNOWLEDGE_URL); it is a
static file, and nothing about us can be learned from downloading it.
Sharing (only if the user turned it on in Sloth Center, off by default): an anonymous report of a setting that
worked or failed. The program's name is not sent, only a fingerprint of it (program_key); the machine's
ID is a random number. The reports are queued, and sloth-windows-prepare sends them,
so starting never waits for the network. The service: services/knowledge/ (in the repository).
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

KNOWLEDGE_URL = "https://raw.githubusercontent.com/Sloth-OS-Linux/sloth-os-knowledge/main/knowledge.json"
REPORT_URL = "https://sloth-os-knowledge.slothos.workers.dev/v1/report"

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "knowledge.json"
QUEUE = sharing.QUEUE
STATE = QUEUE.parent
MACHINE_ID = STATE / "community-id"
MAX_QUEUE = 500

# What we accept from the shared knowledge (the service also allows only these; double protection)
# Proton on/off switches (all with the value "=1"): only these can come from ProtonDB and the reports too
ALLOWED_ENV = {"PROTON_USE_WINED3D", "PROTON_ENABLE_NVAPI", "PROTON_HIDE_NVIDIA_GPU",
               "PROTON_FORCE_LARGE_ADDRESS_AWARE", "PROTON_HEAP_DELAY_FREE", "PROTON_NO_D3D11", "PROTON_NO_D3D10",
               "PROTON_OLD_GL_STRING", "PROTON_NO_WRITE_WATCH"}
ALLOWED_FIXES = ({("verb", v) for v in set(diagnose.DLL_VERBS.values()) | {"dotnet48"}}
                 | {("env", e) for e in ALLOWED_ENV} | {("args", "--disable-gpu")})
_PCI_VENDORS = {"0x1002": "amd", "0x10de": "nvidia", "0x8086": "intel"}


def program_key(exe, names):
    """The program's fingerprint: the (recognized) name and the .exe's name, hashed. That way nobody sees the name."""
    name = identify.normalize(names[0]) if names else ""
    return hashlib.sha256(f"sloth-v1|{name}|{Path(exe).name.lower()}".encode()).hexdigest()


def gpu_vendor():
    """The graphics card's vendor; if there are several (e.g. in a laptop), the discrete one (AMD / NVIDIA) counts."""
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
    return heal.UMU_LINE  # "auto": umu's default


def suggestion(key, gameid=None):
    """The shared knowledge's suggestion for this program and GPU: (Proton line, profile, fixes) or None.

    First the reports of Sloth OS machines (by the program's fingerprint); if there is nothing there, the data
    summarized from ProtonDB (for a recognized game, by Steam AppID; first for this GPU vendor, then for any).
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
    """A report into the queue (only if sharing is turned on)."""
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
        log.warning("shared knowledge (queue): %s", e)


def send_queue():
    """Sends the queued reports (called by sloth-windows-prepare). -> number sent"""
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
                sent += len(batch)  # a bad report: it will not be right if resent either, we drop it
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
