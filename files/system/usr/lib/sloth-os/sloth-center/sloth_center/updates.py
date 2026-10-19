"""Frissítések és visszaállítás: a QML felület vezérlője.

A felület csak emberi nyelvű állapotot és folyamatjelzőt kap; a nyers
rpm-ostree üzenetek a naplóba kerülnek (journalctl --user -t sloth-center).
"""
import json
import logging
import subprocess

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

from . import texts
from .rpmostree import RpmOstree, Transaction

log = logging.getLogger("sloth-center.updates")


class UpdatesController(QObject):
    changed = Signal()

    @Slot()
    def openDiscover(self):
        """Az appok frissítései a Discoverben (a rendszert ez az oldal frissíti)."""
        try:
            subprocess.Popen(["plasma-discover", "--mode", "update"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("Discover: %s", e)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ostree = None
        self._txn = None
        self._mode = ""             # "", "check", "upgrade", "rollback", "background"
        self._status = ""
        self._detail = ""
        self._progress = -1
        self._error = ""
        self._info = ""
        self._current = ""
        self._pending = ""
        self._rollback = ""
        self._available = ""
        self._unavailable = ""
        self._pinned = False
        self._booted_index = -1
        self._versions = []
        try:
            self._ostree = RpmOstree()
            self._ostree.connect_changed(self._on_system_changed)
        except GLib.Error as e:
            log.error("rpm-ostree nem érhető el: %s", e.message)
            self._unavailable = tr("A frissítéskezelő szolgáltatás nem érhető el ezen a gépen.")
        self.refresh()
        self._attach_background()

    # --- Tulajdonságok a QML-nek ------------------------------------------

    # A segéd a jelzést paraméterként kapja: az osztálytörzs nevei (pl. "changed")
    # a benne definiált függvényekből nem látszanak.
    def _p(attr, typ=str, notify=changed):  # noqa: N805 – kis segéd a tulajdonságokhoz
        return Property(typ, lambda self: getattr(self, attr), notify=notify)

    currentVersion = _p("_current")
    pendingVersion = _p("_pending")
    rollbackVersion = _p("_rollback")
    availableVersion = _p("_available")
    statusText = _p("_status")
    detailText = _p("_detail")
    errorText = _p("_error")
    infoText = _p("_info")
    unavailableText = _p("_unavailable")
    progress = _p("_progress", int)
    mode = _p("_mode")
    del _p

    @Property(bool, notify=changed)
    def busy(self):
        return bool(self._mode)

    @Property(bool, notify=changed)
    def needsReboot(self):
        return bool(self._pending)

    @Property(bool, notify=changed)
    def updateAvailable(self):
        return bool(self._available)

    @Property(bool, notify=changed)
    def pinned(self):
        return self._pinned

    @Property(bool, notify=changed)
    def canPin(self):
        return self._booted_index >= 0 and not self._mode

    @Property("QVariantList", notify=changed)
    def versions(self):
        """Az összes gépen lévő verzió: ami most fut, ami legközelebb indul, a megtartottak és az előző."""
        return list(self._versions)

    @Property(bool, notify=changed)
    def canRollback(self):
        return bool(self._rollback) and not self._mode

    # --- Állapot frissítése -----------------------------------------------

    def _on_system_changed(self):
        self.refresh()
        self._attach_background()

    @Slot()
    def refresh(self):
        if not self._ostree:
            self.changed.emit()
            return
        booted = self._ostree.booted()
        default = self._ostree.default()
        rollback = self._ostree.rollback_target()
        self._current = texts.version_text(booted)
        self._pinned = bool(booted.get("pinned"))
        deployments = self._ostree.deployments()
        ids = [d.get("id") for d in deployments]
        self._booted_index = ids.index(booted.get("id")) if booted.get("id") in ids else -1
        self._versions = [{
            "index": i,
            "name": texts.version_text(d),
            "booted": d.get("id") == booted.get("id"),
            # az ostree sorrendjében az első indul a következő újraindításkor
            "next": i == 0,
            "pinned": bool(d.get("pinned")),
        } for i, d in enumerate(deployments)]
        # Ha az alapértelmezett (következő indításkor induló) verzió nem a mostani,
        # akkor újraindítás vár ránk (frissítés vagy visszaállítás után).
        if default and booted and default.get("id") != booted.get("id"):
            self._pending = texts.version_text(default)
        else:
            self._pending = ""
        self._rollback = texts.version_text(rollback) if rollback and rollback.get("id") != booted.get("id") else ""
        cached = self._ostree.cached_update() or {}
        if cached.get("ref-has-new-commit") and not self._pending:
            self._available = texts.version_text(cached) or tr("Új verzió")
        else:
            self._available = ""
        self.changed.emit()

    def _attach_background(self):
        """Ha a háttérben (automatikus frissítés) fut valami, mutassuk az állapotát."""
        if not self._ostree or self._mode:
            return
        address = self._ostree.active_transaction_address()
        if address:
            self._begin("background", tr("A rendszer a háttérben frissül…"))
            self._follow(address)

    # --- Műveletek ----------------------------------------------------------

    def _begin(self, mode, status):
        self._mode = mode
        self._status = status
        self._detail = ""
        self._progress = -1
        self._error = ""
        self._info = ""
        self.changed.emit()

    def _follow(self, address):
        if not address:
            self._finished(True, "")
            return
        self._txn = Transaction(address, self._on_task, self._on_percent,
                                self._on_download, self._finished)

    def _on_task(self, raw):
        log.info("%s", raw)
        self._status = texts.stage_text(raw, self._status)
        self.changed.emit()

    def _on_percent(self, pct):
        self._progress = max(0, min(100, pct))
        self.changed.emit()

    def _on_download(self, transferred, rate):
        self._detail = texts.download_text(transferred, rate)
        self.changed.emit()

    def _on_error(self, raw):
        log.warning("hiba: %s", raw)
        if "in progress" in raw.lower() or "busy" in raw.lower():
            # Valami más már fut: csatlakozzunk rá
            self._mode = ""
            self._attach_background()
            return
        self._mode = ""
        self._error = texts.error_text(raw)
        self.changed.emit()

    def _finished(self, success, raw):
        mode, self._mode, self._txn = self._mode, "", None
        if not success:
            self._on_error(raw or "ismeretlen hiba")
            return
        try:
            self._ostree.reload()
        except GLib.Error:
            pass
        self.refresh()
        # A "naprakész" állapotot a címsor mutatja, ide csak a teendő kerül
        if mode in ("upgrade", "background") and self._pending:
            self._info = tr("A frissítés elkészült. Indítsd újra a gépet, amikor neked megfelel.")
        elif mode == "rollback":
            self._info = tr("Kész. Újraindítás után az előző verzió indul.")
        self.changed.emit()

    @Slot()
    def checkForUpdates(self):
        if self._ostree and not self._mode:
            self._begin("check", tr("Frissítés keresése…"))
            self._ostree.check_update(self._follow, self._on_error)

    @Slot()
    def installUpdate(self):
        if self._ostree and not self._mode:
            self._begin("upgrade", tr("Frissítés keresése…"))
            self._ostree.upgrade(self._follow, self._on_error)

    @Slot()
    def rollback(self):
        if self._ostree and not self._mode:
            self._begin("rollback", tr("Visszaállítás előkészítése…"))
            self._ostree.rollback(self._follow, self._on_error)

    @Slot()
    def cancel(self):
        if self._txn and self._mode in ("check", "upgrade"):
            self._txn.cancel()

    def _helper(self, op, index):
        """Rendszergazdai művelet egy verzión (sloth-helper, grafikus jelszókérővel)."""
        if self._mode or index < 0:
            return False
        self._error, self._info = "", ""
        try:
            r = subprocess.run(["pkexec", "/usr/libexec/sloth-os/sloth-helper-versions", op, str(index)],
                               capture_output=True, text=True, timeout=120)
            ok = json.loads(r.stdout or "{}").get("ok", False)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("%s: %s", op, e)
            ok = False
        if not ok:
            self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        try:
            self._ostree.reload()
        except GLib.Error:
            pass
        self.refresh()
        return ok

    @Slot(bool)
    def setPinned(self, pinned):
        """A mostani verzió megtartása: a frissítések nem törlik (ostree admin pin)."""
        self._helper("pin" if pinned else "unpin", self._booted_index)

    @Slot(int, bool)
    def setVersionPinned(self, index, pinned):
        self._helper("pin" if pinned else "unpin", index)

    @Slot(int)
    def bootVersion(self, index):
        """Egy korábbi (megtartott) verzió induljon a következő újraindításkor. Letöltés nem kell."""
        if self._helper("set-default", index):
            self._info = tr("Kész. Újraindítás után ez a verzió indul.")
            self.changed.emit()

    @Slot()
    def reboot(self):
        """Újraindítás a KDE saját módján (rákérdez a nem mentett munkákra)."""
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        try:
            bus.call_sync("org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown", "logoutAndReboot",
                          None, None, Gio.DBusCallFlags.NONE, 5000, None)
            return
        except GLib.Error as e:
            log.warning("KDE újraindítás nem ment, logind következik: %s", e.message)
        system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        system.call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
                    "Reboot", GLib.Variant("(b)", (True,)), None,
                    Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, -1, None, None)
