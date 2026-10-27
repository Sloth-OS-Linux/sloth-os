"""Updates and rollback: the controller of the QML interface.

The interface only gets a human-language status and a progress bar; the raw
rpm-ostree messages go to the log (journalctl --user -t sloth-center).
"""
import json
import logging
import re
import subprocess

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from sloth_common.apps import packages

from .i18n import tr

from . import texts
from .rpmostree import RpmOstree, Transaction

log = logging.getLogger("sloth-center.updates")
_LAYER_TASK = re.compile(r"\[(\d+)\s*/\s*(\d+)\]\s+Fetching layer\s+\S+\s+\(([^)]+)\)", re.I)


def update_available(cached):
    """Whether there is a new version to download, according to rpm-ostree's CachedUpdate data.

    For a container image (ostree-image-signed:docker://…) "ref-has-new-commit" is always false: there
    "manifest-diff" shows the new version (added / removed layers), as does the "AvailableUpdate" output of
    "rpm-ostree upgrade --check" (2026-10-20, real machine: n-added 29, ref-has-new-commit false)."""
    if cached.get("ref-has-new-commit"):
        return True
    diff = cached.get("manifest-diff") or {}
    return bool(diff.get("n-added") or diff.get("n-removed"))


def download_size(cached):
    """How much the update downloads (the new layers), in bytes; 0 if it is not known."""
    diff = cached.get("manifest-diff") or {}
    try:
        return max(0, int(diff.get("added-size") or 0))
    except (TypeError, ValueError):
        return 0


class UpdatesController(QObject):
    changed = Signal()

    @Slot()
    def openDiscover(self):
        """App updates in Discover (this page updates the system)."""
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
        self._signature_verified = False
        self._available = ""
        self._download_size = 0
        self._metered_warning = False
        self._unavailable = ""
        self._pinned = False
        self._booted_index = -1
        self._versions = []
        try:
            self._ostree = RpmOstree()
            self._ostree.connect_changed(self._on_system_changed)
        except GLib.Error as e:
            log.error("rpm-ostree is not available: %s", e.message)
            self._unavailable = tr("The update service isn't available on this computer.")
        self.refresh()
        self._attach_background()

    # --- Properties for QML ------------------------------------------

    # The helper gets the signal as a parameter: the names of the class body (e.g. "changed")
    # are not visible from the functions defined in it.
    def _p(attr, typ=str, notify=changed):  # noqa: N805 – a small helper for the properties
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

    @Property(str, notify=changed)
    def downloadSize(self):
        """The size of the waiting update ("2,3 GB"), or "" if it is not known."""
        return texts.size_text(self._download_size) if self._download_size else ""

    @Property(bool, notify=changed)
    def meteredWarning(self):
        """The update was started on a mobile or other metered connection: the page asks first."""
        return self._metered_warning

    @Property(bool, notify=changed)
    def signatureVerified(self):
        """Whether the running deployment uses rpm-ostree's signed-image transport."""
        return self._signature_verified

    @Property(bool, notify=changed)
    def pinned(self):
        return self._pinned

    @Property(bool, notify=changed)
    def canPin(self):
        return self._booted_index >= 0 and not self._mode

    @Property("QVariantList", notify=changed)
    def versions(self):
        """Every version on the machine: what runs now, what starts next, the pinned ones and the previous one."""
        return list(self._versions)

    @Property(bool, notify=changed)
    def canRollback(self):
        return bool(self._rollback) and not self._mode

    # --- Refreshing the state -----------------------------------------------

    def _on_system_changed(self):
        self.refresh()
        self._attach_background()

    @Slot()
    def refresh(self):
        if not self._ostree:
            self.changed.emit()
            return
        booted = self._ostree.booted()
        origin = str(booted.get("origin") or "")
        self._signature_verified = origin.startswith("ostree-image-signed:")
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
            # in ostree's order the first one starts at the next restart
            "next": i == 0,
            "pinned": bool(d.get("pinned")),
        } for i, d in enumerate(deployments)]
        # If the default version (the one starting next time) is not the current one,
        # a restart is pending (after an update or a rollback).
        if default and booted and default.get("id") != booted.get("id"):
            self._pending = texts.version_text(default)
        else:
            self._pending = ""
        self._rollback = texts.version_text(rollback) if rollback and rollback.get("id") != booted.get("id") else ""
        cached = self._ostree.cached_update() or {}
        if update_available(cached) and not self._pending:
            self._available = texts.version_text(cached) or tr("New version")
            self._download_size = download_size(cached)
        else:
            self._available = ""
            self._download_size = 0
        self.changed.emit()

    def _attach_background(self):
        """If something runs in the background (automatic update), show its state."""
        if not self._ostree or self._mode:
            return
        address = self._ostree.active_transaction_address()
        if address:
            self._begin("background", tr("The system is updating in the background…"))
            self._follow(address)

    # --- Actions ----------------------------------------------------------

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
        # rpm-ostree's OCI image import reports layer boundaries as task text,
        # but some versions do not emit byte-level DownloadProgress signals.
        # Show the current layer and its size so the progress row is still useful.
        match = _LAYER_TASK.search(raw or "")
        if match:
            current, total, size = match.groups()
            self._detail = f"{current}/{total} · {size}"
            # Without a PercentProgress signal the bar would only sweep back and forth: the finished layers
            # move it forward instead (layer 1 of 29 → 0 %, the last one → 97 %)
            if int(total) > 0:
                self._progress = max(0, min(99, 100 * (int(current) - 1) // int(total)))
        self.changed.emit()

    def _on_percent(self, pct):
        self._progress = max(0, min(100, pct))
        self.changed.emit()

    def _on_download(self, transferred, rate):
        self._detail = texts.download_text(transferred, rate)
        self.changed.emit()

    def _on_error(self, raw):
        log.warning("error: %s", raw)
        if "in progress" in raw.lower() or "busy" in raw.lower():
            # Something else is already running: let us join it
            self._mode = ""
            self._attach_background()
            return
        self._mode = ""
        self._error = texts.error_text(raw)
        self.changed.emit()

    def _finished(self, success, raw):
        mode, self._mode, self._txn = self._mode, "", None
        if not success:
            self._on_error(raw or "unknown error")
            return
        try:
            self._ostree.reload()
        except GLib.Error:
            pass
        self.refresh()
        # The service may still write the state after the transaction ends (the new version found, the prepared
        # version): we look again a bit later, so Sloth Center does not need to be reopened
        for delay in (2000, 8000):
            QTimer.singleShot(delay, self._late_refresh)
        # The "up to date" state is shown by the title; only what needs doing goes here
        if mode in ("upgrade", "background") and self._pending:
            self._info = tr("The update is ready. Restart the computer whenever it suits you.")
        elif mode == "rollback":
            self._info = tr("Done. After a restart, the previous version will start.")
        self.changed.emit()

    def _late_refresh(self):
        if self._mode or not self._ostree:
            return
        try:
            self._ostree.reload()
        except GLib.Error:
            pass
        had_pending = bool(self._pending)
        self.refresh()
        if self._pending and not had_pending and not self._info:
            self._info = tr("The update is ready. Restart the computer whenever it suits you.")
            self.changed.emit()

    @Slot()
    def checkForUpdates(self):
        if self._ostree and not self._mode:
            self._begin("check", tr("Looking for updates…"))
            self._ostree.check_update(self._follow, self._on_error)

    @Slot()
    def installUpdate(self):
        # On a mobile or other metered connection the download can cost money (an update is often several GB):
        # the page asks first. The automatic update in the background skips these connections by itself (uupd).
        if self._ostree and not self._mode and packages.metered():
            self._metered_warning = True
            self.changed.emit()
            return
        self.installUpdateAnyway()

    @Slot()
    def installUpdateAnyway(self):
        self._metered_warning = False
        if self._ostree and not self._mode:
            self._begin("upgrade", tr("Looking for updates…"))
            self._ostree.upgrade(self._follow, self._on_error)
        else:
            self.changed.emit()

    @Slot()
    def dismissMeteredWarning(self):
        self._metered_warning = False
        self.changed.emit()

    @Slot()
    def rollback(self):
        if self._ostree and not self._mode:
            self._begin("rollback", tr("Preparing to roll back…"))
            self._ostree.rollback(self._follow, self._on_error)

    @Slot()
    def cancel(self):
        if self._txn and self._mode in ("check", "upgrade"):
            self._txn.cancel()

    def _helper(self, op, index):
        """An administrator operation on a version (sloth-helper, with a graphical password prompt)."""
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
            self._error = tr("Couldn't change it. This needs administrator approval.")
        try:
            self._ostree.reload()
        except GLib.Error:
            pass
        self.refresh()
        return ok

    @Slot(bool)
    def setPinned(self, pinned):
        """Keeps the current version: updates do not delete it (ostree admin pin)."""
        self._helper("pin" if pinned else "unpin", self._booted_index)

    @Slot(int, bool)
    def setVersionPinned(self, index, pinned):
        self._helper("pin" if pinned else "unpin", index)

    @Slot(int)
    def bootVersion(self, index):
        """An earlier (pinned) version starts at the next restart. No download needed."""
        if self._helper("set-default", index):
            self._info = tr("Done. This version will start after a restart.")
            self.changed.emit()

    @Slot()
    def reboot(self):
        """Restarts the KDE way (asks about unsaved work)."""
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        try:
            bus.call_sync("org.kde.Shutdown", "/Shutdown", "org.kde.Shutdown", "logoutAndReboot",
                          None, None, Gio.DBusCallFlags.NONE, 5000, None)
            return
        except GLib.Error as e:
            log.warning("KDE restart did not work, logind is next: %s", e.message)
        system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        system.call("org.freedesktop.login1", "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
                    "Reboot", GLib.Variant("(b)", (True,)), None,
                    Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, -1, None, None)
