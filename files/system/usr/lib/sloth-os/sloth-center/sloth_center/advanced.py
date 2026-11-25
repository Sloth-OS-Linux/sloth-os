"""Advanced settings: boot menu, memory compression, kernel parameters, system packages (RPM layering).

The graphical equivalent of `rpm-ostree kargs`, `rpm-ostree install/uninstall` and setting up the GRUB
menu. Every change takes effect at the next restart, and on the
Updates page you can go back to the previous version.
"""
import json
import logging
import os
import re
import subprocess
import threading

from gi.repository import GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from sloth_common import driver_options as dopt

from .i18n import N_, tr

from . import restore_points, texts, windowshelper
from .rpmostree import RpmOstree, Transaction

log = logging.getLogger("sloth-center.advanced")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
BOOT_MENU_MARKER = "/var/lib/sloth-os/boot-menu-visible"
ZRAM_CONF = "/etc/systemd/zram-generator.conf"
PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
KARG_RE = re.compile(r"^[A-Za-z0-9_.\-]+(=[A-Za-z0-9_.,:/\-]+)?$")
# The system manages these; the user should not delete them by accident
PROTECTED_KARGS = ("root=", "rootflags=", "ostree=", "rw", "BOOT_IMAGE=", "rd.luks", "resume=")
# The known driver fixes (sloth_common/driver_options.py KNOWN_FIXES), as the user reads them
FIX_TEXTS = {
    "realtek-wifi-power": N_("Wi-Fi keeps dropping: turn off the Realtek Wi-Fi card's power saving ({module})"),
    "realtek-rtw88-aspm": N_("Wi-Fi keeps dropping or is slow: turn off the Realtek Wi-Fi card's link power saving "
                             "({module})"),
    "realtek-rtw89-aspm": N_("Wi-Fi keeps dropping or is slow: turn off the Realtek Wi-Fi card's link power saving "
                             "({module})"),
    "mediatek-mt7921-aspm": N_("Wi-Fi keeps dropping: turn off the MediaTek Wi-Fi card's link power saving "
                               "({module})"),
}
DRIVER_ERRORS = {
    "module": N_("There is no driver with this name on this computer."),
    "param": N_("This driver has no such option. Check the spelling (name=value)."),
    "protected": N_("This driver can't be turned off: the computer needs it to start."),
    "empty": N_("Type the options as name=value, e.g. ips=0."),
}


def _meminfo_gb(key):
    try:
        for line in open("/proc/meminfo"):
            if line.startswith(key + ":"):
                return int(line.split()[1]) / 2 ** 20
    except (OSError, ValueError):
        pass
    return 0.0


def _zram_mode():
    """"default" (Fedora's default), "more" or "off", according to the first line of the file written by sloth-helper."""
    try:
        first = open(ZRAM_CONF, encoding="utf-8").readline()
    except OSError:
        return "default"
    mode = first.removeprefix("# sloth-os: ").split(" ", 1)[0] if first.startswith("# sloth-os: ") else ""
    return mode if mode in ("more", "off") else "custom"


class AdvancedController(QObject):
    changed = Signal()
    _helper_done = Signal(str)

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
        self._zram = "default"
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
    zramMode = Property(str, lambda self: self._zram, notify=changed)

    @Property(str, notify=changed)
    def zramText(self):
        """The size of the memory and of the compressed reserve used now, in plain language."""
        mem = _meminfo_gb("MemTotal")
        size = 0.0
        try:
            size = int(open("/sys/block/zram0/disksize").read()) / 2 ** 30
        except (OSError, ValueError):
            pass
        if size:
            return tr("Memory: {mem} GB. Right now there is a {size} GB compressed reserve next to it.").format(
                mem=f"{mem:.0f}", size=f"{size:.1f}".rstrip("0").rstrip("."))
        return tr("Memory: {mem} GB. There is no compressed reserve right now.").format(mem=f"{mem:.0f}")

    # --- Next to Windows: the Windows-side boot helper ------------------------------------

    @Property(bool, notify=changed)
    def windowsPresent(self):
        """Whether there is an NTFS partition on the machine (a machine installed next to Windows)."""
        if not hasattr(self, "_windows_present"):
            self._windows_present = bool(windowshelper.ntfs_filesystems())
            self._helper_text = ""
            self._helper_done.connect(self._on_helper_done)
        return self._windows_present

    @Property(str, notify=changed)
    def windowsHelperText(self):
        return getattr(self, "_helper_text", "")

    @Slot()
    def placeWindowsHelper(self):
        self._helper_text = tr("Looking for the Windows partition…")
        self.changed.emit()
        threading.Thread(target=lambda: self._helper_done.emit(windowshelper.place()), daemon=True).start()

    def _on_helper_done(self, result):
        self._helper_text = {
            "placed": tr("Done. Start Windows, and on the desktop, in the “Sloth OS” folder, double-click the "
                         "Sloth-OS-boot file (it asks for administrator approval). You only need to do this once."),
            "readonly": tr("The Windows partition is read-only right now because Windows was hibernated or shut down "
                           "with fast startup. Start Windows, shut it down completely (Shift + Shut down), then try "
                           "again."),
            "none": tr("We didn't find Windows on this computer."),
        }.get(result, tr("That didn't work. Please try again later."))
        self.changed.emit()

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
        self._zram = _zram_mode()
        self.changed.emit()

    # --- Boot menu ------------------------------------------------------------------

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
            self._error = tr("Couldn't change it. This needs administrator approval.")
        self.refresh()

    # --- Driver options (sloth_common.driver_options; from the next start) ------------------------------------

    @Property("QVariantList", notify=changed)
    def driverOptions(self):
        """The chosen ones: [{"module", "text" (the options, or "Turned off"), "off"}]."""
        return [{"module": e["module"], "off": bool(e.get("off")),
                 "text": tr("Turned off") if e.get("off")
                 else " ".join(f"{k}={v}" for k, v in sorted((e.get("options") or {}).items()))}
                for e in dopt.load()]

    @Property("QVariantList", notify=changed)
    def driverFixes(self):
        """The known fixes for this computer's drivers, not applied yet: [{"id", "module", "text"}]."""
        return [{"id": f["id"], "module": f["module"], "text": tr(FIX_TEXTS.get(f["id"], f["text"]), module=f["module"])}
                for f in dopt.suggestions()]

    def _save_drivers(self, entries):
        self._error, self._info = "", ""
        try:
            r = subprocess.run(["pkexec", HELPER, "driver-options"], input=json.dumps({"entries": entries}),
                               capture_output=True, text=True, timeout=60)
            result = json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("driver-options: %s", e)
            result = {}
        if result.get("ok"):
            self._info = tr("Saved. Takes effect after the next restart.")
        elif result.get("error") in DRIVER_ERRORS:
            self._error = tr(DRIVER_ERRORS[result["error"]])
        else:
            self._error = tr("Couldn't change it. This needs administrator approval.")
        self.refresh()

    def _without(self, module):
        return [e for e in dopt.load() if e["module"] != module]

    @Slot(str, str)
    def applyDriverFix(self, fix_id, module):
        entry = dopt.fix_entry(fix_id, module)
        if entry:
            self._save_drivers(self._without(module) + [entry])

    @Slot(str, str)
    def addDriverOption(self, module, options):
        module = module.strip().replace("-", "_")
        parsed = dopt.parse_options(options)
        if not dopt.MODULE_RE.match(module):
            self._error, self._info = tr(DRIVER_ERRORS["module"]), ""
        elif parsed is None:
            self._error, self._info = tr(DRIVER_ERRORS["empty"]), ""
        else:
            self._save_drivers(self._without(module) + [{"module": module, "options": parsed, "off": False}])
            return
        self.changed.emit()

    @Slot(str)
    def turnOffDriver(self, module):
        module = module.strip().replace("-", "_")
        if not dopt.MODULE_RE.match(module):
            self._error, self._info = tr(DRIVER_ERRORS["module"]), ""
            self.changed.emit()
            return
        self._save_drivers(self._without(module) + [{"module": module, "options": {}, "off": True}])

    @Slot(str)
    def removeDriverOption(self, module):
        self._save_drivers(self._without(module))

    # --- Memory compression (zram) -------------------------------------------------------

    @Slot(str)
    def setZramMode(self, mode):
        self._error, self._info = "", ""
        try:
            r = subprocess.run(["pkexec", HELPER, "zram", mode], capture_output=True, text=True, timeout=60)
            ok = json.loads(r.stdout or "{}").get("ok", False)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("zram: %s", e)
            ok = False
        if ok:
            self._info = tr("Saved. Takes effect after the next restart.")
        else:
            self._error = tr("Couldn't change it. This needs administrator approval.")
        self.refresh()

    # --- Transactions (kernel parameter, package) ----------------------------------------

    def _run(self, start, done_text, reason):
        """reason: the restore point made first (restore_points.before_change: kernel-args, packages)."""
        if not self._ostree or self._busy:
            return
        self._busy, self._error, self._info = True, "", ""
        self._status, self._progress = tr("Making a restore point…"), -1
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
                log.warning("transaction: %s", raw)
                self._error = self._pkg_error(raw) or texts.error_text(raw)
            self.refresh()

        def on_address(address):
            self._txn = Transaction(address, on_task, on_percent, lambda *a: None, on_finished)

        def go():
            self._status = tr("Preparing…")
            self.changed.emit()
            start(on_address, lambda raw: on_finished(False, raw))

        restore_points.before_change(reason, go)

    @staticmethod
    def _pkg_error(raw):
        low = (raw or "").lower()
        if "no package" in low or "not found" in low or "no match" in low:
            return tr("There's no package with that name in the Fedora repository. Check the name.")
        if "already" in low and "requested" in low:
            return tr("This package is already installed.")
        return ""

    @Slot(str)
    def addKernelArg(self, arg):
        arg = arg.strip()
        if not KARG_RE.match(arg):
            self._error = tr("That's not a valid kernel parameter (e.g. “nomodeset” or “amdgpu.ppfeaturemask=0xffffffff”).")
            self.changed.emit()
            return
        self._run(lambda a, e: self._ostree.set_kernel_args([arg], [], a, e),
                  tr("Done. The new setting takes effect after the next restart."), "kernel-args")

    @Slot(str)
    def removeKernelArg(self, arg):
        if arg.startswith(PROTECTED_KARGS):
            return
        self._run(lambda a, e: self._ostree.set_kernel_args([], [arg], a, e),
                  tr("Done. The change takes effect after the next restart."), "kernel-args")

    @Slot(str)
    def addPackage(self, name):
        names = [n for n in re.split(r"[\s,]+", name.strip()) if n]
        if not names or not all(PKG_RE.match(n) for n in names):
            self._error = tr("Enter a valid package name (e.g. “htop”).")
            self.changed.emit()
            return
        self._run(lambda a, e: self._ostree.pkg_change(names, [], a, e),
                  tr("Done. The package will be available after the next restart."), "packages")

    @Slot(str)
    def removePackage(self, name):
        if PKG_RE.match(name):
            self._run(lambda a, e: self._ostree.pkg_change([], [name], a, e),
                      tr("Done. The package will be gone after the next restart."), "packages")
