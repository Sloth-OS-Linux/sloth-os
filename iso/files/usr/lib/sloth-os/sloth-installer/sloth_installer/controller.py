"""A Sloth OS telepítő vezérlője (QML <-> Python).

Lépések: welcome (nyelv) -> region (billentyűzet, időzóna) -> disk -> confirm -> install -> done | error.
A tényleges telepítést a sloth-install-helper végzi rendszergazdaként (pkexec);
innen csak emberi nyelvű állapot és folyamatjelző látszik.
"""
import json
import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Property, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from sloth_common.i18n import Catalog

from . import system

log = logging.getLogger("sloth-installer")

HELPER = "/usr/libexec/sloth-os/sloth-install-helper"
PAGES = ["welcome", "region", "disk", "confirm", "install", "done", "error"]
catalog = Catalog(Path(__file__).resolve().parent / "translations")


class InstallerController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = "welcome"
        self._languages = system.languages()
        self._keyboards = system.keyboards()
        self._timezones = system.timezones()
        self._language = "en"
        self._keyboard = "us"
        self._timezone = "UTC"
        self._keyboard_chosen = False   # ha a felhasználó maga választott, a nyelvváltás nem írja felül
        self._timezone_chosen = False
        self._disks = []
        self._disk = ""
        self._confirmed = False
        self._stage = ""
        self._progress = 0
        self._error = ""
        self._proc = None
        self._buffer = b""
        start = catalog.system_language()
        self.setLanguage(start if any(l["code"] == start for l in self._languages) else "en")

    # --- Tulajdonságok -------------------------------------------------------------

    page = Property(str, lambda self: self._page, notify=changed)
    languages = Property("QVariantList", lambda self: self._languages, constant=True)
    keyboards = Property("QVariantList", lambda self: self._keyboards, constant=True)
    timezones = Property("QVariantList", lambda self: self._timezones, constant=True)
    language = Property(str, lambda self: self._language, notify=changed)
    keyboard = Property(str, lambda self: self._keyboard, notify=changed)
    timezone = Property(str, lambda self: self._timezone, notify=changed)
    disks = Property("QVariantList", lambda self: self._disks, notify=changed)
    disk = Property(str, lambda self: self._disk, notify=changed)
    confirmed = Property(bool, lambda self: self._confirmed, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    strings = Property("QVariantMap", lambda self: catalog.strings(), notify=changed)

    @Property(str, notify=changed)
    def statusText(self):
        return catalog.tr(f"stage.{self._stage}") if self._stage else ""

    @Property(str, notify=changed)
    def errorText(self):
        return catalog.tr(self._error) if self._error else ""

    @Property("QVariantMap", notify=changed)
    def diskInfo(self):
        return next((d for d in self._disks if d["path"] == self._disk), {})

    # --- Választások -----------------------------------------------------------------

    @Slot(str)
    def setLanguage(self, code):
        lang = next((l for l in self._languages if l["code"] == code), None)
        if not lang:
            return
        self._language = code
        catalog.set_language(code)
        if not self._keyboard_chosen:
            self._keyboard = lang["keyboard"]
        if not self._timezone_chosen:
            self._timezone = lang["timezone"]
        QApplication.setApplicationDisplayName(catalog.tr("app.title"))
        QApplication.setLayoutDirection(Qt.LayoutDirection.RightToLeft if catalog.is_rtl()
                                        else Qt.LayoutDirection.LeftToRight)
        self.changed.emit()

    @Slot(str)
    def setKeyboard(self, kbd):
        self._keyboard, self._keyboard_chosen = kbd, True
        self.changed.emit()

    @Slot(str)
    def setTimezone(self, tz):
        self._timezone, self._timezone_chosen = tz, True
        self.changed.emit()

    @Slot()
    def refreshDisks(self):
        try:
            self._disks = system.disks()
        except Exception as e:  # lsblk hiba: üres listát mutatunk, a felület szól
            log.error("lemezek: %s", e)
            self._disks = []
        usable = [d for d in self._disks if not d["tooSmall"]]
        if self._disk not in {d["path"] for d in usable}:
            # ha csak egy belső lemez van, azt előre kijelöljük
            internal = [d for d in usable if not d["removable"]]
            self._disk = internal[0]["path"] if len(internal) == 1 else ""
        self.changed.emit()

    @Slot(str)
    def selectDisk(self, path):
        if any(d["path"] == path and not d["tooSmall"] for d in self._disks):
            self._disk = path
            self._confirmed = False
            self.changed.emit()

    @Slot(bool)
    def setConfirmed(self, value):
        self._confirmed = value
        self.changed.emit()

    # --- Navigáció ----------------------------------------------------------------------

    @Slot()
    def next(self):
        order = PAGES[:4]
        log.info("tovább: %s (lemez: %s)", self._page, self._disk or "-")
        if self._page in order[:-1]:
            self._page = order[order.index(self._page) + 1]
            if self._page == "disk":
                self.refreshDisks()
            self.changed.emit()

    @Slot()
    def back(self):
        order = PAGES[:4]
        log.info("vissza: %s", self._page)
        if self._page in order[1:]:
            self._page = order[order.index(self._page) - 1]
            self.changed.emit()

    @Slot()
    def install(self):
        log.info("telepítés indítása: %s, %s, %s, %s", self._disk, self._language, self._keyboard, self._timezone)
        if self._proc or not self._disk or not self._confirmed:
            return
        locale = next(l["locale"] for l in self._languages if l["code"] == self._language)
        self._page, self._stage, self._progress, self._error = "install", "start", 0, ""
        self.changed.emit()
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._finished)
        args = [HELPER, "install", "--disk", self._disk, "--locale", locale,
                "--keyboard", self._keyboard, "--timezone", self._timezone]
        if os.environ.get("SLOTH_INSTALL_DRY_RUN") == "1":
            # próbaüzem: jelszókérés és lemeztörlés nélkül
            self._proc.start(HELPER, args[1:])
        else:
            self._proc.start("pkexec", args)

    def _read(self):
        self._buffer += bytes(self._proc.readAllStandardOutput())
        *lines, self._buffer = self._buffer.split(b"\n")
        for raw in lines:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "stage" in msg:
                self._stage = msg["stage"]
                self._progress = int(msg.get("progress", self._progress))
            elif msg.get("done"):
                self._progress, self._page = 100, "done"
            elif "error" in msg:
                self._error = msg["error"]
            self.changed.emit()

    def _finished(self, code, _status):
        self._proc = None
        if self._page == "done":
            return
        # 126/127: a jelszókérést megszakították vagy nem kaptunk jogot
        if not self._error:
            self._error = "error.not_authorized" if code in (126, 127) else "error.install_failed"
        self._page = "error"
        self.changed.emit()

    @Slot()
    def retry(self):
        self._page, self._error = "confirm", ""
        self.changed.emit()

    @Slot()
    def reboot(self):
        QProcess.startDetached("systemctl", ["reboot"])

    @Slot()
    def quit(self):
        if not self._proc:
            QApplication.quit()
