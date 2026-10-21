"""A gép alaphelyzetbe állítása: „Fájljaim megtartásával” vagy „Mindent töröl” (a Windows megfelelője).

Az előkészítés (a legújabb verzió letöltése, a kézzel hozzáadott rendszercsomagok és kernelparaméterek levétele)
most fut, a sloth-helperen át, rendszergazdai jóváhagyással; a többi a következő induláskor, bejelentkezés előtt
(factory-reset boot). Amíg nem indult újra a gép, vissza lehet vonni.
"""
import json
import logging
import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import N_, tr

log = logging.getLogger("sloth-center.reset")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
STATE = Path("/var/lib/sloth-os/factory-reset.json")
NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def password_hash(password):
    """SHA-512 crypt hash, mint a telepítőben (a jelszó csak a bemeneten megy át)."""
    r = subprocess.run(["openssl", "passwd", "-6", "-stdin"], input=password + "\n",
                       capture_output=True, text=True, timeout=30)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.startswith("$6$") else ""


def pending_mode():
    try:
        mode = json.loads(STATE.read_text()).get("mode", "")
    except (OSError, ValueError):
        return ""
    return mode if mode in ("keep", "all") else ""


class ResetController(QObject):
    changed = Signal()
    _stage = Signal(str)
    _done = Signal(object)

    STAGES = {
        "download": N_("Downloading the newest system version… Depending on your connection this may take a few minutes."),
        "packages": N_("Removing manually added system packages…"),
        "kargs": N_("Restoring kernel parameters…"),
    }
    # induláskor a factory-reset írja ki a Plymouth-animáció alá (a fordítást innen veszi)
    BOOT_TEXTS = {
        N_("Resetting this PC… This may take a few minutes, don't turn off the computer."),
        N_("Done. Restarting…"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        self._status = ""
        self._error = ""
        self._pending = pending_mode()
        self._stage.connect(self._on_stage)
        self._done.connect(self._on_done)

    busy = Property(bool, lambda self: self._busy, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    pendingMode = Property(str, lambda self: self._pending, notify=changed)

    @Slot(str, result=str)
    def checkAccount(self, username):
        """Hibaüzenet a felhasználónévhez, vagy üres szöveg, ha jó."""
        if not NAME_RE.match(username):
            return tr("The username must start with a lowercase letter and contain only lowercase letters, digits, "
                      "hyphens or underscores (no spaces or accents).")
        return ""

    @Slot(str, str, str, str)
    def start(self, mode, fullname, username, password):
        if self._busy or mode not in ("keep", "all"):
            return
        self._error = ""
        request = {"backup_name": tr("Old settings")}
        if mode == "all":
            pwhash = password_hash(password) if password else ""
            if self.checkAccount(username) or not pwhash or ":" in fullname or "\n" in fullname:
                self._error = tr("That didn't work. Check the new account's details.")
                self.changed.emit()
                return
            request["account"] = {"username": username, "fullname": fullname.strip() or username,
                                  "password_hash": pwhash}
        self._busy, self._status = True, tr("Preparing…")
        self.changed.emit()

        def work():
            result = {"ok": False, "error": "no-result"}
            try:
                p = subprocess.Popen(["pkexec", HELPER, "factory-reset", mode], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                p.stdin.write(json.dumps(request))
                p.stdin.close()
                for line in p.stdout:
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if "stage" in msg:
                        self._stage.emit(msg["stage"])
                    else:
                        result = msg
                err = p.stderr.read()
                p.wait()
                if err.strip():
                    log.info("factory-reset: %s", err.strip()[-2000:])
            except OSError as e:
                result = {"ok": False, "error": str(e)}
            self._done.emit(result)

        threading.Thread(target=work, daemon=True).start()

    def _on_stage(self, stage):
        self._status = tr(self.STAGES.get(stage, "Előkészítés…"))
        self.changed.emit()

    def _on_done(self, result):
        self._busy, self._status = False, ""
        if not result.get("ok"):
            log.warning("alaphelyzet: %s", result.get("error"))
            if result.get("error") == "no-result":
                self._error = tr("That didn't work. This needs administrator approval.")
            else:
                self._error = tr("Couldn't prepare the reset. Check your internet connection and try again.")
        self._pending = pending_mode()
        self.changed.emit()

    @Slot()
    def cancel(self):
        self._error = ""
        try:
            r = subprocess.run(["pkexec", HELPER, "factory-reset-cancel"], capture_output=True, text=True,
                               timeout=600)
            ok = json.loads(r.stdout or "{}").get("ok", False)
        except (OSError, subprocess.SubprocessError, ValueError):
            ok = False
        if not ok:
            self._error = tr("That didn't work. This needs administrator approval.")
        self._pending = pending_mode()
        self.changed.emit()

    @Slot()
    def restartNow(self):
        subprocess.Popen(["systemctl", "reboot"])
