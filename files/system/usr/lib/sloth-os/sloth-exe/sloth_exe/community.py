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
import urllib.error
import urllib.request
from pathlib import Path

from sloth_common import knowledge, sharing

from . import diagnose, heal, identify

log = logging.getLogger("sloth-exe.community")

KNOWLEDGE_URL = "https://raw.githubusercontent.com/Sloth-OS-Linux/sloth-os-knowledge/main/knowledge.json"
REPORT_URL = "https://sloth-os-knowledge.slothos.workers.dev/v1/report"

# shared with Steam games' fixes (sloth_common/knowledge.py)
CACHE = knowledge.CACHE
QUEUE = sharing.QUEUE
ALLOWED_ENV = knowledge.ALLOWED_ENV
gpu_vendor = knowledge.gpu_vendor
ALLOWED_FIXES = ({("verb", v) for v in set(diagnose.DLL_VERBS.values()) | {"dotnet48"}}
                 | {("env", e) for e in ALLOWED_ENV} | {("args", "--disable-gpu")})


def program_key(exe, names):
    """The program's fingerprint: the (recognized) name and the .exe's name, hashed. That way nobody sees the name."""
    name = identify.normalize(names[0]) if names else ""
    return hashlib.sha256(f"sloth-v1|{name}|{Path(exe).name.lower()}".encode()).hexdigest()


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
    entry = knowledge.entry(key, gameid, gpu_vendor(), CACHE)
    if not entry:
        return None
    line, profile = entry.get("line"), entry.get("profile")
    fixes = [tuple(f) for f in entry.get("fixes", []) if isinstance(f, list) and tuple(f) in ALLOWED_FIXES]
    if line not in (heal.UMU_LINE, heal.GE_LINE) or profile not in heal.PROFILES:
        return None
    return line, profile, fixes


def queue_report(key, attempt, outcome):
    """A report into the queue (only if sharing is turned on)."""
    fixes = [tuple(f) for f in attempt.fixes if tuple(f) in ALLOWED_FIXES]
    knowledge.queue_report(key, _line(heal.resolved_name(attempt)), attempt.profile, fixes, outcome)


def send_queue():
    """Sends the queued reports (called by sloth-windows-prepare): the Windows programs' and the Steam games',
    each only while its own sharing is on (sloth_common/sharing.py). -> number sent"""
    return (_send(QUEUE) if sharing.enabled() else 0) + (_send(sharing.GAMES_QUEUE) if sharing.games_enabled() else 0)


def _send(queue):
    if not queue.exists():
        return 0
    items = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines() if line.strip()]
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
        queue.write_text("".join(json.dumps(x) + "\n" for x in rest), encoding="utf-8")
    else:
        queue.unlink(missing_ok=True)
    return sent
