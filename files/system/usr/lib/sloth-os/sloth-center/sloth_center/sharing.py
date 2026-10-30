"""Sharing a folder on the home network (Disks page): other computers (Windows, Mac, a TV) open it with the user name
and a password, or, if the user chose so, without one.

Turning it on always asks for the administrator password (org.slothos.helper.sharing), and that one password does
everything (sloth-helper share-add): the usershares group, the Samba password and
the share; no new sign-in is needed. /usr/libexec/sloth-os/file-sharing then starts Samba for the local network only
and writes the account's shares into /run/sloth-os/sharing/<uid>.json, which this page reads.
"""
import json
import logging
import os
import re
import socket
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.sharing")

HELPER = "/usr/libexec/sloth-os/sloth-helper-sharing"
STATUS = Path("/run/sloth-os/sharing") / f"{os.getuid()}.json"
HOME_PREFIXES = ("/var/home/", "/home/")


def read_status():
    try:
        data = json.loads(STATUS.read_text())
        return list(data.get("shares", [])), bool(data.get("password"))
    except (OSError, ValueError):
        return [], False


def share_name(path):
    """The folder's name as a share name Windows accepts (letters, digits, _ . -)."""
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", os.path.basename(path.rstrip("/"))).strip("-.") or "Share"
    return name[:80] if name[0].isalnum() else ("S" + name)[:80]


class SharingController(QObject):
    changed = Signal()
    _done = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shares, self._password = read_status()
        self._busy = False
        self._message = ""
        self._problem = False
        self._done.connect(self._on_done)

    shares = Property("QVariantList", lambda self: [dict(s, address=self.address(s["name"])) for s in self._shares],
                      notify=changed)
    hasPassword = Property(bool, lambda self: self._password, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    problem = Property(bool, lambda self: self._problem, notify=changed)
    user = Property(str, lambda self: os.environ.get("USER") or os.getlogin(), constant=True)

    @Slot(str, result=str)
    def address(self, name):
        return f"\\\\{socket.gethostname().split('.')[0]}\\{name}"

    @Slot()
    def refresh(self):
        self._shares, self._password = read_status()
        self.changed.emit()

    @Slot(str, bool, bool, str)
    def addShare(self, folder_url, write, guests, password):
        path = unquote(urlsplit(folder_url).path) if folder_url.startswith("file:") else folder_url
        if not path:
            return
        if not guests and not password and not self._password:
            self._report(False, tr("Set a password for other computers first."))
            return
        names = {s["name"].lower() for s in self._shares}
        name, n = share_name(path), 2
        base = name
        while name.lower() in names:
            name, n = f"{base[:76]}-{n}", n + 1
        request = json.dumps({"name": name, "path": path, "write": write, "guests": guests, "password": password})
        self._run(["share-add"], request)

    @Slot(str)
    def removeShare(self, name):
        self._run(["share-remove", name], None)

    def _run(self, args, stdin):
        if self._busy:
            return
        self._busy, self._message = True, ""
        self.changed.emit()

        def work():
            try:
                r = subprocess.run(["pkexec", HELPER, *args], input=stdin, capture_output=True, text=True,
                                   timeout=300)
                result = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as e:
                log.warning("sharing: %s", e)
                result = {}
            if result.get("ok"):
                self._done.emit(True, "")
                return
            error = result.get("error", "")
            log.warning("sharing failed: %s", error)
            if not result:   # the password window was cancelled
                self._done.emit(False, "")
            elif error == "not owner":
                self._done.emit(False, tr("Only your own folders can be shared."))
            elif error == "password needed":
                self._done.emit(False, tr("Set a password for other computers first."))
            else:
                self._done.emit(False, tr("Couldn't share the folder."))

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, ok, message):
        self._busy = False
        self._shares, self._password = read_status()
        self._report(ok, message)

    def _report(self, ok, message):
        self._message, self._problem = message, not ok and bool(message)
        self.changed.emit()
