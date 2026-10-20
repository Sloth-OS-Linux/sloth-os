"""Fájlmentés: a saját fájlok óránkénti mentése (Btrfs-pillanatképek), a mentett állapotok böngészése.

A Windows „Korábbi verziók” / „Fájlelőzmények” megfelelője. A pillanatképeket a home-snapshots készíti
időzítővel (sloth_common.snapshots); a be- és kikapcsolás, a megtartás, a „Mentés most” és a törlés a
sloth-helperen át megy (rendszergazdai jóváhagyással). A listázáshoz nem kell jelszó.
"""
import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from sloth_common import snapshots as snap

from . import texts
from .i18n import tr

log = logging.getLogger("sloth-center.backup")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
# Mentés külső lemezre: a Pika Backup (Flathub), a Discoverből telepítve
PIKA = "org.gnome.World.PikaBackup"
PIKA_DESKTOP = [Path("/var/lib/flatpak/exports/share/applications") / f"{PIKA}.desktop",
                Path.home() / ".local/share/flatpak/exports/share/applications" / f"{PIKA}.desktop"]


def pika_installed():
    return any(p.exists() for p in PIKA_DESKTOP)


def own_home_rel():
    """A saját mappa útja a /var/home-hoz képest (a pillanatképen belül ugyanott van)."""
    try:
        return Path(os.path.realpath(Path.home())).relative_to(snap.HOME_ROOT)
    except ValueError:
        return None


class BackupController(QObject):
    changed = Signal()
    _done = Signal(str, object)   # a háttérszálból: (művelet, eredmény)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "unsupported"
        self._cfg = dict(snap.DEFAULTS)
        self._snapshots = []
        self._busy = False
        self._error = ""
        self._info = ""
        self._pika = False
        # a Discoverben indított telepítés után 5 mp-enként megnézzük, kész-e (legfeljebb 15 percig)
        self._pika_timer = QTimer(self, interval=5000)
        self._pika_timer.timeout.connect(self._check_pika)
        self._pika_checks = 0
        self._done.connect(self._on_done)
        self.refresh()

    state = Property(str, lambda self: self._state, notify=changed)
    enabled = Property(bool, lambda self: self._cfg["enabled"], notify=changed)
    keep = Property(str, lambda self: self._cfg["keep"], notify=changed)
    snapshots = Property("QVariantList", lambda self: list(self._snapshots), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    pikaInstalled = Property(bool, lambda self: self._pika, notify=changed)

    @Slot()
    def refresh(self):
        self._state = snap.state()
        self._pika = pika_installed()
        self._cfg = snap.load_config()
        rel = own_home_rel()
        self._snapshots = []
        for name, when in snap.list_snapshots():
            path = snap.SNAP_DIR / name / rel if rel else None
            self._snapshots.append({"name": name, "dateText": texts.datetime_text(when),
                                    "path": str(path) if path and path.is_dir() else ""})
        self.changed.emit()

    def _helper(self, action, args, success=""):
        if self._busy:
            return
        self._busy, self._error, self._info = True, "", ""
        self.changed.emit()

        def work():
            try:
                r = subprocess.run(["pkexec", HELPER, *args], capture_output=True, text=True, timeout=900)
                result = json.loads(r.stdout or "{}")
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                result = {"ok": False, "error": str(e)}
            result["success"] = success
            self._done.emit(action, result)

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, action, result):
        self._busy = False
        if result.get("ok"):
            self._info = result["success"]
        else:
            log.warning("%s: %s", action, result.get("error"))
            if result.get("error") == "no-space":
                self._error = tr("Nincs elég szabad hely a lemezen az új mentéshez. Szabadíts fel helyet, és próbáld újra.")
            elif result.get("error") == "not-ready":
                self._error = tr("A mentés a következő újraindítás után indul.")
            else:
                self._error = tr("Nem sikerült. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    @Slot(bool)
    def setEnabled(self, on):
        self._helper("snapshots", ["snapshots", "on" if on else "off"])

    @Slot(str)
    def setKeep(self, keep):
        if keep in snap.KEEP_DAYS and keep != self._cfg["keep"]:
            self._helper("snapshots-keep", ["snapshots-keep", keep])

    @Slot()
    def takeNow(self):
        self._helper("snapshot-now", ["snapshot-now"], tr("Kész: elmentettem a fájljaid mostani állapotát."))

    @Slot()
    def deleteAll(self):
        self._helper("snapshots-delete-all", ["snapshots-delete-all"], tr("Kész: a mentett állapotok törölve."))

    @Slot(str)
    def openFolder(self, path):
        if path:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- Mentés külső lemezre (Pika Backup) -------------------------------------------------------------

    @Slot()
    def installPika(self):
        subprocess.Popen(["plasma-discover", f"appstream://{PIKA}"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._pika_checks = 0
        self._pika_timer.start()

    def _check_pika(self):
        self._pika_checks += 1
        if pika_installed() or self._pika_checks > 180:
            self._pika_timer.stop()
            self.refresh()

    @Slot()
    def openPika(self):
        subprocess.Popen(["flatpak", "run", PIKA], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
