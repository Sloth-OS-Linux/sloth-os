"""Drivers and hardware: recognizing the graphics card, switching between the NVIDIA and AMD/Intel versions,
enrolling the Secure Boot key (needed for the NVIDIA driver).
"""
import json
import logging
import re
import subprocess
from pathlib import Path

from gi.repository import GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

from . import texts
from .rpmostree import RpmOstree, Transaction

log = logging.getLogger("sloth-center.drivers")

NVIDIA_AUTO_STATE = Path("/var/lib/sloth-os/nvidia-auto")
VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}
PCI_IDS = Path("/usr/share/hwdata/pci.ids")
HELPER = "/usr/libexec/sloth-os/sloth-helper"
PHONE_LINK = "/usr/libexec/sloth-os/phone-link"   # connecting a phone (KDE Connect), per user
SB_KEY = "/etc/pki/akmods/certs/akmods-ublue.der"


def _pci_name(vendor, device):
    """The device name from pci.ids (e.g. "GeForce RTX 5060")."""
    v, d = vendor[2:].lower(), device[2:].lower()
    try:
        in_vendor = False
        with PCI_IDS.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                if not line.startswith("\t"):
                    in_vendor = line.lower().startswith(v + " ")
                elif in_vendor and not line.startswith("\t\t") and line[1:].lower().startswith(d + " "):
                    name = line[1:].split(" ", 1)[1].strip()
                    m = re.search(r"\[([^\]]+)\]", name)  # "AD106 [GeForce RTX 4060 Ti]" -> the part in brackets
                    return m.group(1) if m else name
    except OSError:
        pass
    return ""


def detect_gpus():
    gpus = []
    for dev in sorted(Path("/sys/bus/pci/devices").glob("*")):
        try:
            cls = (dev / "class").read_text().strip()
            if not cls.startswith("0x03"):
                continue
            vendor = (dev / "vendor").read_text().strip()
            device = (dev / "device").read_text().strip()
        except OSError:
            continue
        brand = VENDORS.get(vendor, tr("Other"))
        name = _pci_name(vendor, device)
        gpus.append({"brand": brand, "name": f"{brand} {name}".strip() if name and brand not in name else (name or brand)})
    return gpus


def _mokutil(*args):
    try:
        r = subprocess.run(["mokutil", *args], capture_output=True, text=True, timeout=15)
        return (r.stdout + r.stderr).lower()
    except (OSError, subprocess.SubprocessError):
        return ""


class DriversController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gpus = detect_gpus()
        self._image = ""
        self._ostree = None
        self._txn = None
        self._busy = False
        self._status = ""
        self._progress = -1
        self._info = ""
        self._error = ""
        self._sb = {"secureBoot": False, "enrolled": None, "pending": False}
        try:
            self._ostree = RpmOstree()
            booted = self._ostree.booted()
            self._image = str(booted.get("container-image-reference") or booted.get("origin") or "")
        except GLib.Error as e:
            log.warning("rpm-ostree: %s", e.message)
        # The state of the automatic NVIDIA switch (/usr/libexec/sloth-os/nvidia-auto): do not offer it a second time
        try:
            auto = NVIDIA_AUTO_STATE.read_text().strip()
        except OSError:
            auto = ""
        if auto == "downloading":
            self._busy, self._status, self._progress = True, tr("Downloading the new edition…"), -1
        elif auto in ("ready", "ready-mok") and not self.nvidiaImage:
            self._info = "switched"
        self.refreshSecureBoot()
        self._phone = self._phone_link("status")

    # --- Properties ---------------------------------------------------------

    phoneLinkAvailable = Property(bool, lambda self: Path(PHONE_LINK).is_file(), constant=True)
    phoneLink = Property(bool, lambda self: self._phone, notify=changed)

    gpus = Property("QVariantList", lambda self: list(self._gpus), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)

    @Property(bool, notify=changed)
    def hasNvidia(self):
        return any(g["brand"] == "NVIDIA" for g in self._gpus)

    @Property(bool, notify=changed)
    def nvidiaImage(self):
        return "sloth-os-nvidia" in self._image

    @Property(bool, notify=changed)
    def canSwitch(self):
        return bool(re.search(r"sloth-os(-nvidia)?:", self._image)) and self._ostree is not None

    @Property(bool, notify=changed)
    def mismatch(self):
        """The wrong version runs: there is an NVIDIA card but not the NVIDIA image (or the other way round)."""
        return self.canSwitch and self.hasNvidia != self.nvidiaImage

    @Property(bool, notify=changed)
    def secureBoot(self):
        return bool(self._sb.get("secureBoot"))

    @Property(bool, notify=changed)
    def keyNeeded(self):
        """Secure Boot is on, the NVIDIA image runs, and the key is not enrolled yet."""
        return self.secureBoot and self.nvidiaImage and self._sb.get("enrolled") is False \
            and not self._sb.get("pending")

    @Property(bool, notify=changed)
    def keyPending(self):
        return bool(self._sb.get("pending"))

    # --- Secure Boot -------------------------------------------------------------

    @Slot()
    @staticmethod
    def _phone_link(action):
        try:
            return subprocess.run([PHONE_LINK, action], capture_output=True, timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("phone-link %s: %s", action, e)
            return False

    @Slot(bool)
    def setPhoneLink(self, on):
        """Connecting a phone (KDE Connect) for the user; no password needed."""
        self._error = ""
        if not self._phone_link("on" if on else "off"):
            self._error = tr("Couldn't change it.")
        self._phone = self._phone_link("status")
        self.changed.emit()

    def refreshSecureBoot(self):
        sb = _mokutil("--sb-state")
        state = {"secureBoot": "secureboot enabled" in sb, "enrolled": None, "pending": False}
        if Path(SB_KEY).exists():
            t = _mokutil("--test-key", SB_KEY)
            state["enrolled"] = "already enrolled" in t
            state["pending"] = "already in the enrollment request" in t
        self._sb = state
        self.changed.emit()

    @Slot()
    def enrollKey(self):
        self._error = ""
        try:
            r = subprocess.run(["pkexec", HELPER, "secureboot-enroll"], capture_output=True, text=True, timeout=300)
            result = json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("secureboot-enroll: %s", e)
            result = {"ok": False}
        if result.get("ok"):
            self._info = "enrolled"
        elif r.returncode in (126, 127):
            self._error = tr("This needs administrator approval. Try again and enter your password.")
        else:
            self._error = tr("Couldn't prepare the key enrollment. Try again.")
        self.refreshSecureBoot()

    # --- Switching the version -----------------------------------------------------------

    @Slot()
    def switchVariant(self):
        if not self.canSwitch or self._busy:
            return
        to_nvidia = not self.nvidiaImage
        if to_nvidia:
            target = re.sub(r"sloth-os:", "sloth-os-nvidia:", self._image, count=1)
        else:
            target = self._image.replace("sloth-os-nvidia:", "sloth-os:", 1)
        self._busy, self._error, self._info = True, "", ""
        self._status = tr("Downloading the new edition…")
        self._progress = -1
        self.changed.emit()

        def on_task(raw):
            log.info("%s", raw)
            self._status = texts.stage_text(raw, self._status)
            self.changed.emit()

        def on_percent(p):
            self._progress = p
            self.changed.emit()

        def on_download(t, rate):
            self._info = texts.download_text(t, rate)
            self.changed.emit()

        def on_finished(ok, raw):
            self._busy, self._txn = False, None
            if ok:
                self._info = "switched"
            else:
                log.warning("rebase: %s", raw)
                self._error = texts.error_text(raw)
            self.changed.emit()

        def on_address(address):
            self._txn = Transaction(address, on_task, on_percent, on_download, on_finished)

        def on_error(raw):
            on_finished(False, raw)

        self._ostree.rebase(target, on_address, on_error)
