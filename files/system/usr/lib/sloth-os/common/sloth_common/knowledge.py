"""The shared knowledge, the parts both kinds of games use: Windows programs (sloth-exe/community.py) and Steam
games (steam_doctor.py).

Reading: knowledge.json, downloaded by sloth-windows-prepare from the public knowledge repository (KNOWLEDGE_URL in
community.py): "programs" are the reports of Sloth OS machines (by a fingerprint, never a name), "games" the
settings summarized from ProtonDB, by Steam AppID ("umu-<appid>"), per GPU vendor or "any".
Sharing (only if the user turned it on, sharing.enabled()): a report goes into the queue, and sloth-windows-prepare
sends it (community.send_queue). The service accepts only the settings listed here (services/knowledge/worker.js).
"""
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path

from sloth_common import sharing

log = logging.getLogger("sloth.knowledge")

CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "knowledge.json"
QUEUE = sharing.QUEUE
STATE = QUEUE.parent
MACHINE_ID = STATE / "community-id"
MAX_QUEUE = 500

LINES = ("UMU-Proton", "GE-Proton")
# The settings profiles (environment variables), the same as sloth-exe's heal.PROFILES
PROFILES = {
    "default": {},
    "nofsync": {"PROTON_NO_FSYNC": "1", "PROTON_NO_ESYNC": "1"},
    "wined3d": {"PROTON_USE_WINED3D": "1"},
}
# Proton on/off switches (all with the value "=1"): only these can come from ProtonDB and the reports
ALLOWED_ENV = {"PROTON_USE_WINED3D", "PROTON_ENABLE_NVAPI", "PROTON_HIDE_NVIDIA_GPU",
               "PROTON_FORCE_LARGE_ADDRESS_AWARE", "PROTON_HEAP_DELAY_FREE", "PROTON_NO_D3D11", "PROTON_NO_D3D10",
               "PROTON_OLD_GL_STRING", "PROTON_NO_WRITE_WATCH"}
_PCI_VENDORS = {"0x1002": "amd", "0x10de": "nvidia", "0x8086": "intel"}


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


def machine_id():
    """The machine's random ID for the reports (one vote per machine); made on first use."""
    try:
        value = MACHINE_ID.read_text().strip()
        uuid.UUID(value)
        return value
    except (OSError, ValueError):
        value = str(uuid.uuid4())
        STATE.mkdir(parents=True, exist_ok=True)
        MACHINE_ID.write_text(value)
        return value


def steam_key(appid):
    """A Steam game's fingerprint in the reports (the same on every machine, nothing about the user in it)."""
    return hashlib.sha256(f"sloth-v1|steam|{appid}".encode()).hexdigest()


def load(path=None):
    try:
        data = json.loads(Path(path or CACHE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def config_of(entry):
    """A setting as (line, profile, fixes): the same setting compares equal whatever else the entry holds."""
    fixes = tuple(sorted(tuple(f) for f in entry.get("fixes") or [] if isinstance(f, (list, tuple)) and len(f) == 2))
    return entry.get("line"), entry.get("profile"), fixes


def status(key=None, gameid=None, gpu=None, path=None, data=None):
    """The best known setting and the best one left out because it was reported not to work anymore.

    In order: Sloth OS machines' reports for `key` on this GPU vendor, then ProtonDB's summary for `gameid`
    ("umu-<appid>") on this vendor, then for any. A setting listed under "disputed" for `key` and this vendor
    (it failed on several Sloth OS machines lately) is skipped, also when it comes from ProtonDB.
    -> (entry or None, disputed entry or None). An entry is a copy with "source" ("sloth" or "protondb") and
    "players" (the machines or reports behind it) added; "last" ("2026-09") when the data has it.
    data: knowledge.json already loaded (when asking about many games)."""
    data = data if data is not None else load(path)
    gpu = gpu or gpu_vendor()
    disputed = set()
    for cfg in (((data.get("disputed") or {}).get(key) or {}).get(gpu) or []) if key else []:
        if isinstance(cfg, dict):
            disputed.add(config_of(cfg))
    candidates = []
    if key:
        candidates.append(("sloth", ((data.get("programs") or {}).get(key) or {}).get(gpu)))
    if gameid:
        game = (data.get("games") or {}).get(gameid) or {}
        candidates += [("protondb", game.get(gpu)), ("protondb", game.get("any"))]
    usable = skipped = None
    for source, found in candidates:
        if not isinstance(found, dict) or found.get("line") not in LINES or found.get("profile") not in PROFILES:
            continue
        found = {**found, "source": source,
                 "players": found.get("machines") if source == "sloth" else found.get("reports")}
        if config_of(found) in disputed:
            skipped = skipped or found
            continue
        usable = found
        break
    return usable, skipped


def entry(key=None, gameid=None, gpu=None, path=None):
    """The best known setting that was not reported to stop working (status()), or None."""
    return status(key, gameid, gpu, path)[0]


def queue_report(program, line, profile, fixes, outcome, games=False):
    """A report into the queue, only if that sharing is turned on (games: a Steam game's, sharing.games_enabled).
    fixes: [(kind, value)], already allowed ones."""
    allowed, queue = (sharing.games_enabled(), sharing.GAMES_QUEUE) if games else (sharing.enabled(), QUEUE)
    if not program or not allowed or line not in LINES or profile not in PROFILES:
        return
    item = {"machine": machine_id(), "program": program, "gpu": gpu_vendor(), "line": line, "profile": profile,
            "fixes": sorted([list(f) for f in fixes]), "outcome": outcome}
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        lines = queue.read_text(encoding="utf-8").splitlines() if queue.exists() else []
        lines = (lines + [json.dumps(item)])[-MAX_QUEUE:]
        queue.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as e:
        log.warning("shared knowledge (queue): %s", e)
