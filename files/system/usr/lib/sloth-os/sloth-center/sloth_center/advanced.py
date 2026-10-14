"""Haladó beállítások: boot menü, kernelparaméterek, rendszercsomagok (RPM rétegezés).

Az `rpm-ostree kargs`, `rpm-ostree install/uninstall` és a GRUB menü beállításának
grafikus megfelelője. Minden változás a következő újraindításkor lép életbe, és a
Frissítések oldalon vissza lehet állni az előző verzióra.
"""
import json
import logging
import os
import re
import subprocess

from gi.repository import GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

from . import texts
from .rpmostree import RpmOstree, Transaction

log = logging.getLogger("sloth-center.advanced")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
BOOT_MENU_MARKER = "/var/lib/sloth-os/boot-menu-visible"
PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
KARG_RE = re.compile(r"^[A-Za-z0-9_.\-]+(=[A-Za-z0-9_.,:/\-]+)?$")
# Ezeket a rendszer kezeli; a felhasználó ne törölje véletlenül
PROTECTED_KARGS = ("root=", "rootflags=", "ostree=", "rw", "BOOT_IMAGE=", "rd.luks", "resume=")


class AdvancedController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ostree = None
        self._txn = None
        self._busy = False
        self._status = ""
        self._progress = -1
        self._error = ""
        self._info = ""
        self._kargs = []
        self._packages = []
        self._boot_visible = os.path.exists(BOOT_MENU_MARKER)
        try:
            self._ostree = RpmOstree()
        except GLib.Error as e:
            log.warning("rpm-ostree: %s", e.message)
        self.refresh()

    busy = Property(bool, lambda self: self._busy, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    kernelArgs = Property("QVariantList", lambda self: list(self._kargs), notify=changed)
    packages = Property("QVariantList", lambda self: list(self._packages), notify=changed)
    bootMenuVisible = Property(bool, lambda self: self._boot_visible, notify=changed)

    @Slot()
    def refresh(self):
        if self._ostree:
            try:
                self._ostree.reload()
            except GLib.Error:
                pass
            args = self._ostree.kernel_args_string().split()
            self._kargs = [{"arg": a, "protected": a.startswith(PROTECTED_KARGS)} for a in args]
            self._packages = self._ostree.layered_packages()
        self._boot_visible = os.path.exists(BOOT_MENU_MARKER)
        self.changed.emit()

    # --- Boot menü ------------------------------------------------------------------

    @Slot(bool)
    def setBootMenuVisible(self, visible):
        self._error = ""
        try:
            r = subprocess.run(["pkexec", HELPER, "boot-menu", "visible" if visible else "hidden"],
                               capture_output=True, text=True, timeout=60)
            ok = json.loads(r.stdout or "{}").get("ok", False)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("boot-menu: %s", e)
            ok = False
        if not ok:
            self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    # --- Tranzakciók (kernelparaméter, csomag) ----------------------------------------

    def _run(self, start, done_text):
        if not self._ostree or self._busy:
            return
        self._busy, self._error, self._info = True, "", ""
        self._status, self._progress = tr("Előkészítés…"), -1
        self.changed.emit()

        def on_task(raw):
            log.info("%s", raw)
            self._status = texts.stage_text(raw, self._status)
            self.changed.emit()

        def on_percent(p):
            self._progress = p
            self.changed.emit()

        def on_finished(ok, raw):
            self._busy, self._txn = False, None
            if ok:
                self._info = done_text
            else:
                log.warning("tranzakció: %s", raw)
                self._error = self._pkg_error(raw) or texts.error_text(raw)
            self.refresh()

        def on_address(address):
            self._txn = Transaction(address, on_task, on_percent, lambda *a: None, on_finished)

        start(on_address, lambda raw: on_finished(False, raw))

    @staticmethod
    def _pkg_error(raw):
        low = (raw or "").lower()
        if "no package" in low or "not found" in low or "no match" in low:
            return tr("Ilyen nevű csomag nincs a Fedora tárolóban. Ellenőrizd a nevet.")
        if "already" in low and "requested" in low:
            return tr("Ez a csomag már telepítve van.")
        return ""

    @Slot(str)
    def addKernelArg(self, arg):
        arg = arg.strip()
        if not KARG_RE.match(arg):
            self._error = tr("Ez nem érvényes kernelparaméter (pl. „nomodeset” vagy „amdgpu.ppfeaturemask=0xffffffff”).")
            self.changed.emit()
            return
        self._run(lambda a, e: self._ostree.set_kernel_args([arg], [], a, e),
                  tr("Kész. Az új beállítás a következő újraindítás után lép életbe."))

    @Slot(str)
    def removeKernelArg(self, arg):
        if arg.startswith(PROTECTED_KARGS):
            return
        self._run(lambda a, e: self._ostree.set_kernel_args([], [arg], a, e),
                  tr("Kész. A változás a következő újraindítás után lép életbe."))

    @Slot(str)
    def addPackage(self, name):
        names = [n for n in re.split(r"[\s,]+", name.strip()) if n]
        if not names or not all(PKG_RE.match(n) for n in names):
            self._error = tr("Adj meg egy érvényes csomagnevet (pl. „htop”).")
            self.changed.emit()
            return
        self._run(lambda a, e: self._ostree.pkg_change(names, [], a, e),
                  tr("Kész. A csomag a következő újraindítás után lesz elérhető."))

    @Slot(str)
    def removePackage(self, name):
        if PKG_RE.match(name):
            self._run(lambda a, e: self._ostree.pkg_change([], [name], a, e),
                      tr("Kész. A csomag a következő újraindítás után tűnik el."))
