"""The guest account (Account and security): a friend can use the computer without seeing your files.

One switch: sloth-helper-family's guest-on / guest-off (pkexec, the administrator password, or none in the "users"
topic). The guest signs in without a password, is never an administrator, and everything it leaves behind is
deleted when it signs out and at every start (/usr/libexec/sloth-os/guest-reset).
"""
import getpass
import grp
import json
import logging
import pwd
import subprocess
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

from sloth_common.guest import guest

from .i18n import tr

log = logging.getLogger("sloth-center.guest")

HELPER = "/usr/libexec/sloth-os/sloth-helper-family"


def guest_exists():
    g = guest()
    if not g:
        return False
    try:
        return pwd.getpwnam(g["user"]).pw_uid == g["uid"]
    except KeyError:
        return False


class GuestController(QObject):
    changed = Signal()
    _done = Signal(bool, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self._admin = getpass.getuser() in grp.getgrnam("wheel").gr_mem
        except KeyError:
            self._admin = False
        self._on = guest_exists()
        self._busy = False
        self._error = ""
        self._done.connect(self._on_done)

    isAdmin = Property(bool, lambda self: self._admin, notify=changed)
    on = Property(bool, lambda self: self._on, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)

    @Slot(bool)
    def setOn(self, on):
        if self._busy or on == self._on:
            return
        self._busy, self._error = True, ""
        self.changed.emit()

        def work():
            args = ["guest-on"] if on else ["guest-off"]
            request = json.dumps({"fullname": tr("Guest")}) if on else ""
            try:
                r = subprocess.run(["pkexec", HELPER, *args], input=request, capture_output=True, text=True,
                                   timeout=300)
                result = json.loads(r.stdout or "{}")
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                log.warning("%s: %s", args[0], e)
                result = {}
            self._done.emit(on, result)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, on, result):
        self._busy = False
        if result.get("ok"):
            self._on = on
        elif result.get("error") == "exists":
            self._error = tr("There's already an account called \"guest\" on this computer, so Sloth OS doesn't "
                             "touch it.")
        elif not result:
            self._error = tr("Couldn't change it. This needs administrator approval.")
        else:
            log.warning("guest: %s", result.get("error"))
            self._error = tr("Couldn't change it. Try again, or restart the computer if it keeps happening.")
        self._on = guest_exists()
        self.changed.emit()
