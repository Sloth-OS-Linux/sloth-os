"""Sharing a folder on the home network (Disks page): other computers (Windows, Mac, a TV) open it with the user name
and a password, or, if the user chose so, without one.

Turning it on always asks for the administrator password (org.slothos.helper.sharing), and that one password does
everything (sloth-helper share-add): the usershares group, the Samba password and
the share; no new sign-in is needed. /usr/libexec/sloth-os/file-sharing then starts Samba for the local network only
and writes the account's shares into /run/sloth-os/sharing/<uid>.json, which this page reads.

Every network has a kind, as in Windows (file-sharing): home (the folders open, the computer is announced), private
(they open, not announced), public (hidden), or public with sharing allowed (asked once). The networks and whether
sharing is on at all are in /run/sloth-os/sharing/state.json. A network's kind needs no password
(org.slothos.helper.network); turning sharing on or off does (org.slothos.helper.sharing).
"""
import json
import grp
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
NETWORK_HELPER = "/usr/libexec/sloth-os/sloth-helper-network"
STATUS = Path("/run/sloth-os/sharing") / f"{os.getuid()}.json"
STATE = Path("/run/sloth-os/sharing/state.json")
HOME_PREFIXES = ("/var/home/", "/home/")
# the network kinds on which shared folders open (file-sharing's OPEN_KINDS)
OPEN_KINDS = ("home", "private", "public-shared")


def read_status():
    try:
        data = json.loads(STATUS.read_text())
        return list(data.get("shares", [])), bool(data.get("password"))
    except (OSError, ValueError):
        return [], False


def read_state():
    """{"enabled", "reachable", "networks": [{uuid, name, kind, connected}]}; sharing is on if nothing says so."""
    try:
        data = json.loads(STATE.read_text())
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    networks = [n for n in data.get("networks", []) if isinstance(n, dict) and n.get("uuid")]
    # the connected ones first, then by name
    networks.sort(key=lambda n: (not n.get("connected"), str(n.get("name", "")).casefold()))
    return {"enabled": data.get("enabled") is not False, "reachable": bool(data.get("reachable")),
            "networks": networks}


def local_groups():
    """Groups NSS can resolve, including Winbind-provided AD groups."""
    try:
        groups = grp.getgrall()
    except OSError:
        groups = []
    result = [{"name": group.gr_name, "gid": group.gr_gid} for group in groups
              if group.gr_gid >= 1000 and group.gr_name != "usershares"
              and (group.gr_gid < 60000 or "\\" in group.gr_name)]
    return sorted({group["gid"]: group for group in result}.values(), key=lambda item: item["name"].casefold())


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
        self._state = read_state()
        self._busy = False
        self._message = ""
        self._problem = False
        self._done.connect(self._on_done)

    shares = Property("QVariantList", lambda self: [dict(s, address=self.address(s["name"])) for s in self._shares],
                      notify=changed)
    groups = Property("QVariantList", lambda self: local_groups(), notify=changed)
    hasPassword = Property(bool, lambda self: self._password, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    problem = Property(bool, lambda self: self._problem, notify=changed)
    user = Property(str, lambda self: os.environ.get("USER") or os.getlogin(), constant=True)
    enabled = Property(bool, lambda self: self._state["enabled"], notify=changed)
    networks = Property("QVariantList", lambda self: self._state["networks"], notify=changed)

    def _connected(self):
        return [n for n in self._state["networks"] if n.get("connected")]

    def _public(self):
        """The connected network if the shared folders are closed on every connected one (public, or not asked yet),
        else {}: then sharing here asks first."""
        connected = self._connected()
        if not connected or any(n.get("kind") in OPEN_KINDS for n in connected):
            return {}
        return {"uuid": connected[0]["uuid"], "name": connected[0]["name"]}

    onPublic = Property(bool, lambda self: bool(self._public()), notify=changed)
    publicNetwork = Property("QVariantMap", lambda self: self._public(), notify=changed)

    @Slot(str, result=str)
    def address(self, name):
        return f"\\\\{socket.gethostname().split('.')[0]}\\{name}"

    @Slot()
    def refresh(self):
        # only when something changed: the page asks every few seconds, and rebuilding the lists would close an
        # open network menu
        new = read_status(), read_state()
        if new != ((self._shares, self._password), self._state):
            (self._shares, self._password), self._state = new
            self.changed.emit()

    @Slot(bool)
    def setEnabled(self, on):
        if on != self._state["enabled"]:
            self._run(["sharing", "on" if on else "off"], None, error=tr("Couldn't change folder sharing."))

    @Slot(str, str)
    def setNetworkKind(self, uuid, kind):
        self._run(["network-kind", uuid, kind], None, helper=NETWORK_HELPER, error=tr("Couldn't change the network."))

    @Slot(str, bool, bool, str, "QVariantList")
    def addShare(self, folder_url, write, guests, password, groups):
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
        request = json.dumps({"name": name, "path": path, "write": write, "guests": guests,
                              "password": password, "groups": groups})
        self._run(["share-add"], request)

    @Slot(str)
    def removeShare(self, name):
        self._run(["share-remove", name], None)

    def _run(self, args, stdin, helper=HELPER, error=None):
        if self._busy:
            return
        self._busy, self._message = True, ""
        self.changed.emit()
        failed = error or tr("Couldn't share the folder.")

        def work():
            try:
                r = subprocess.run(["pkexec", helper, *args], input=stdin, capture_output=True, text=True,
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
                self._done.emit(False, failed)

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, ok, message):
        self._busy = False
        self._shares, self._password = read_status()
        self._state = read_state()
        self._report(ok, message)

    def _report(self, ok, message):
        self._message, self._problem = message, not ok and bool(message)
        self.changed.emit()
