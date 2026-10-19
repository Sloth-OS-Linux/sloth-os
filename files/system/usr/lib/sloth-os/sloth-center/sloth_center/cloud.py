"""Felhőtárhely (OneDrive, Google Drive) mappaként: Fiók és biztonság → Felhőtárhely.

A munkát a /usr/libexec/sloth-os/cloud-drive végzi (rclone, felhasználónként, jelszó nélkül). A bejelentkezés a
böngészőben történik; amíg a felhasználó ott végez, a felület vár (háttérszálon).
"""
import json
import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.cloud")

CLOUD_DRIVE = "/usr/libexec/sloth-os/cloud-drive"
NAMES = {"onedrive": "OneDrive", "gdrive": "Google Drive"}


class CloudController(QObject):
    changed = Signal()
    _done = Signal(str, str, object)   # a háttérszálból: (művelet, szolgáltatás, eredmény)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drives = []
        self._busy = ""      # épp melyik szolgáltatáson dolgozunk
        self._error = ""
        self._info = ""
        self._done.connect(self._on_done)
        self.refresh()

    drives = Property("QVariantList", lambda self: list(self._drives), notify=changed)
    busy = Property(str, lambda self: self._busy, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Slot()
    def refresh(self):
        try:
            r = subprocess.run([CLOUD_DRIVE, "list"], capture_output=True, text=True, timeout=30)
            drives = json.loads(r.stdout or "[]")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("cloud-drive list: %s", e)
            drives = []
        self._drives = [dict(d, name=NAMES.get(d["service"], d["service"])) for d in drives]
        self.changed.emit()

    def _run(self, action, service):
        self._busy, self._error, self._info = service, "", ""
        if action == "add":
            self._info = tr("Jelentkezz be a megnyíló böngészőablakban. Ha végeztél, itt folytatódik magától.")
        self.changed.emit()

        def work():
            try:
                r = subprocess.run([CLOUD_DRIVE, action, service], capture_output=True, text=True, timeout=900)
                result = json.loads(r.stdout or "{}")
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                result = {"ok": False, "error": str(e)}
            self._done.emit(action, service, result)

        threading.Thread(target=work, daemon=True).start()

    @Slot(str)
    def connectDrive(self, service):
        self._run("add", service)

    @Slot(str)
    def disconnectDrive(self, service):
        self._run("remove", service)

    def _on_done(self, action, service, result):
        self._busy, self._info = "", ""
        if not result.get("ok"):
            log.warning("cloud-drive %s %s: %s", action, service, result.get("error"))
            self._error = tr("Nem sikerült. Ellenőrizd az internetkapcsolatot, és próbáld újra.")
        elif action == "add":
            self._info = tr("Kész: a fájljaid a(z) {folder} mappában vannak.", folder=result["folder"])
        self.refresh()
