"""Lemezek: meghajtók, foglaltság, egészség (SMART), felesleges fájlok törlése.

A `df`, `smartctl` és `flatpak uninstall --unused` grafikus megfelelője.
A meghajtók adatai a UDisks2 D-Bus felületéről jönnek (olvasáshoz nem kell jelszó).
"""
import logging
import os
import subprocess
import threading

import gi

from sloth_common import windows_import

from .i18n import tr

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, Gio, GLib  # noqa: E402
from PySide6.QtCore import QObject, Property, Signal, Slot  # noqa: E402

log = logging.getLogger("sloth-center.disks")

UD = "org.freedesktop.UDisks2"


def _size_text(n):
    for unit, div in (("TB", 1000 ** 4), ("GB", 1000 ** 3), ("MB", 1000 ** 2)):
        if n >= div:
            v = n / div
            return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + f" {unit}"
    return f"{n} B"


def list_drives():
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    objs = bus.call_sync(UD, "/org/freedesktop/UDisks2", "org.freedesktop.DBus.ObjectManager",
                         "GetManagedObjects", None, None, Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
    drives = {}
    for path, ifs in objs.items():
        d = ifs.get(UD + ".Drive")
        if not d or not d.get("Size"):
            continue
        health, temp = "ok", 0
        nvme = ifs.get(UD + ".NVMe.Controller")
        ata = ifs.get(UD + ".Drive.Ata")
        if nvme:
            if nvme.get("SmartCriticalWarning"):
                health = "failing"
            temp = nvme.get("SmartTemperature", 0)
        elif ata and ata.get("SmartEnabled"):
            if ata.get("SmartFailing"):
                health = "failing"
            temp = ata.get("SmartTemperature", 0)
        kind = "SSD" if d.get("RotationRate") == 0 else tr("Merevlemez")
        if d.get("Removable") or d.get("MediaRemovable"):
            kind = tr("Cserélhető meghajtó")
        drives[path] = {"name": (d.get("Vendor", "") + " " + d.get("Model", "")).strip() or tr("Meghajtó"),
                        "kind": kind, "size": d["Size"], "health": health,
                        "temp": round(temp - 273.15) if temp else 0, "mounts": [], "used": 0, "total": 0}

    for path, ifs in objs.items():
        fs, block = ifs.get(UD + ".Filesystem"), ifs.get(UD + ".Block")
        if not fs or not block or block.get("Drive") not in drives:
            continue
        mounts = [bytes(m).rstrip(b"\0").decode(errors="replace") for m in fs.get("MountPoints", [])]
        if not mounts:
            continue
        drive = drives[block["Drive"]]
        drive["mounts"].append(mounts[0])
        try:
            st = os.statvfs(mounts[0])
            drive["total"] += st.f_blocks * st.f_frsize
            drive["used"] += (st.f_blocks - st.f_bfree) * st.f_frsize
        except OSError:
            pass

    out = []
    for d in sorted(drives.values(), key=lambda x: ("/" not in x["mounts"], x["name"])):
        total = d["total"] or d["size"]
        d["usedPercent"] = round(100 * d["used"] / total) if d["total"] else 0
        d["usageText"] = tr("{used} foglalt / {total}, {free} szabad", used=_size_text(d["used"]),
                            total=_size_text(d["total"]), free=_size_text(d["total"] - d["used"])) \
            if d["total"] else tr("{size}, nincs csatlakoztatva", size=_size_text(d["size"]))
        d["system"] = "/" in d["mounts"] or "/var" in d["mounts"] or "/sysroot" in d["mounts"]
        d["openPath"] = next((m for m in d["mounts"] if m not in ("/", "/boot", "/boot/efi", "/sysroot")),
                             os.path.expanduser("~") if d["system"] else "")
        out.append(d)
    return out


def unused_flatpak_refs():
    refs = []
    for inst in (Flatpak.Installation.new_system(None), Flatpak.Installation.new_user(None)):
        try:
            for r in inst.list_unused_refs(None, None):
                refs.append((inst, r))
        except GLib.Error as e:
            log.warning("unused refs: %s", e.message)
    return refs


class DisksController(QObject):
    changed = Signal()
    _drives_ready = Signal(object)
    _cleanup_ready = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drives = []
        self._cleanup = ""
        self._cleanup_size = 0
        self._busy = False
        self._drives_ready.connect(self._on_drives)
        self._cleanup_ready.connect(self._on_cleanup)
        # van-e a gépen Windows-partíció (fájlok áthozása; csatolás nélkül nézzük)
        self._windows = bool(windows_import.candidates())
        self.refresh()

    drives = Property("QVariantList", lambda self: list(self._drives), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    cleanupText = Property(str, lambda self: self._cleanup, notify=changed)
    hasWindows = Property(bool, lambda self: self._windows, constant=True)

    @Slot()
    def importFromWindows(self):
        """A fájlok áthozása a Windowsból: az Üdvözlő ezzel az egy lépéssel (sloth_welcome, --windows-import)."""
        subprocess.Popen(["sloth-welcome", "--windows-import"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot()
    def refresh(self):
        def work():
            try:
                drives = list_drives()
            except GLib.Error as e:
                log.warning("udisks: %s", e.message)
                drives = []
            self._drives_ready.emit(drives)
        threading.Thread(target=work, daemon=True).start()

    def _on_drives(self, drives):
        self._drives = drives
        self.changed.emit()

    @Slot(str)
    def openFolder(self, path):
        if path:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot()
    def cleanup(self):
        """A már egy app által sem használt Flatpak összetevők törlése."""
        if self._busy:
            return
        self._busy = True
        self._cleanup = tr("Felesleges fájlok keresése…")
        self.changed.emit()

        def work():
            refs = unused_flatpak_refs()
            if not refs:
                self._cleanup_ready.emit(None, tr("Nincs mit törölni, minden rendben."))
                return
            freed = sum(r.get_installed_size() for _i, r in refs)
            by_inst = {}
            for inst, r in refs:
                by_inst.setdefault(inst.get_id(), (inst, []))[1].append(r.format_ref())
            try:
                for inst, names in by_inst.values():
                    txn = Flatpak.Transaction.new_for_installation(inst, None)
                    for n in names:
                        txn.add_uninstall(n)
                    txn.run(None)
                self._cleanup_ready.emit(None, tr("Kész! {size} hely szabadult fel.", size=_size_text(freed)))
            except GLib.Error as e:
                log.warning("cleanup: %s", e.message)
                self._cleanup_ready.emit(None, tr("Nem sikerült mindent törölni. Próbáld újra később."))

        threading.Thread(target=work, daemon=True).start()

    def _on_cleanup(self, _unused, text):
        self._busy = False
        self._cleanup = text
        self.changed.emit()
        self.refresh()
