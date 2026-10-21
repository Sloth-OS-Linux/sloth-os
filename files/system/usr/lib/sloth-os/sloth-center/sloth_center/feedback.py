"""Feedback: a bug, an idea or something else, from Sloth Center (Feedback page).

The shared knowledge service (services/knowledge, POST /v1/feedback) opens a GitHub issue from it; the user does
not need a GitHub account. If they ask for it, the log goes too (the contents of "Save log", its end), but not into the issue: the
service stores it separately, and only the developers can open it.
"""
import json
import logging
import os
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from . import health
from .i18n import catalog

log = logging.getLogger("sloth-center.feedback")

URL = "https://sloth-os-knowledge.slothos.workers.dev/v1/feedback"
MAX_LOG = 500 * 1024  # the service accepts at most 512 KB; the end of the log matters more
# The service looks at the size of the whole request (512 + 64 KB), not the log's: JSON encoding can blow the log up
# (Wine logs' backslashes are doubled), so we keep the encoded request under the limit too
MAX_BODY = 560 * 1024
KINDS = ("bug", "idea", "other")


def _version():
    try:
        for line in Path("/usr/lib/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')[:120]
    except OSError:
        pass
    return ""


def _log_text():
    fd, path = tempfile.mkstemp(prefix="sloth-feedback-", suffix=".txt")
    os.close(fd)
    try:
        health.write_log(path, lines=3000)
        data = Path(path).read_bytes()
    finally:
        os.unlink(path)
    return data[-MAX_LOG:].decode("utf-8", "replace")


def _encode(body):
    """The request's bytes; if it is too big, it cuts from the start of the log (every character removed is at least 1 byte)."""
    data = json.dumps(body, ensure_ascii=False).encode()
    while len(data) > MAX_BODY and body.get("log"):
        body["log"] = body["log"][len(data) - MAX_BODY:]
        data = json.dumps(body, ensure_ascii=False).encode()
    return data


def send(kind, text, attach_log):
    """(ok, number or error code). Network error: (False, "network"); too many: (False, "rate")."""
    body = {"kind": kind, "text": text, "version": _version(), "lang": catalog.language()[:20]}
    if attach_log:
        body["log"] = _log_text()
    # A custom User-Agent is needed: Cloudflare blocks Python's default ("Python-urllib") (403, error 1010)
    req = urllib.request.Request(URL, data=_encode(body), method="POST",
                                 headers={"content-type": "application/json", "user-agent": "SlothOS-Center/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return True, json.load(resp).get("number", 0)
    except urllib.error.HTTPError as e:
        log.warning("feedback: HTTP %s", e.code)
        return False, "rate" if e.code == 429 else "server"
    except (OSError, ValueError) as e:
        log.warning("feedback: %s", e)
        return False, "network"


class FeedbackController(QObject):
    changed = Signal()
    _done = Signal(bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._result = ""   # "" | "sent" | "network" | "rate" | "server"
        self._number = 0
        self._done.connect(self._on_done)

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def result(self):
        return self._result

    @Property(int, notify=changed)
    def number(self):
        return self._number

    @Slot(str, str, bool)
    def send(self, kind, text, attach_log):
        if self._busy or kind not in KINDS or len(text.strip()) < 10:
            return
        self._busy, self._result = True, ""
        self.changed.emit()
        threading.Thread(target=lambda: self._done.emit(*send(kind, text.strip()[:5000], attach_log)),
                         daemon=True).start()

    @Slot()
    def reset(self):
        self._result, self._number = "", 0
        self.changed.emit()

    def _on_done(self, ok, value):
        self._busy = False
        if ok:
            self._result, self._number = "sent", int(value or 0)
        else:
            self._result = str(value)
        self.changed.emit()
