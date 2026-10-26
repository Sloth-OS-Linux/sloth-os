"""Disks: drives, usage, health (SMART), deleting unneeded files.

The graphical equivalent of `df`, `smartctl` and `flatpak uninstall --unused`.
The drives' data comes from UDisks2's D-Bus interface (reading needs no password).
"""
import logging
import os
import subprocess
import threading
from pathlib import Path

import gi

from sloth_common import windows_import
from sloth_common.apps import library

from .health import smart_state
from .i18n import tr
from .rpmostree import RpmOstree, Transaction

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
        # the same verdict as System health; a worn drive still counts as healthy here
        health = "failing" if smart_state(ifs) == "failing" else "ok"
        temp = (ifs.get(UD + ".NVMe.Controller") or ifs.get(UD + ".Drive.Ata") or {}).get("SmartTemperature", 0)
        kind = "SSD" if d.get("RotationRate") == 0 else tr("Hard disk")
        if d.get("Removable") or d.get("MediaRemovable"):
            kind = tr("Removable drive")
        drives[path] = {"name": (d.get("Vendor", "") + " " + d.get("Model", "")).strip() or tr("Drive"),
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
        d["usageText"] = tr("{used} used / {total}, {free} free", used=_size_text(d["used"]),
                            total=_size_text(d["total"]), free=_size_text(d["total"] - d["used"])) \
            if d["total"] else tr("{size}, not mounted", size=_size_text(d["size"]))
        d["system"] = "/" in d["mounts"] or "/var" in d["mounts"] or "/sysroot" in d["mounts"]
        d["openPath"] = next((m for m in d["mounts"] if m not in ("/", "/boot", "/boot/efi", "/sysroot")),
                             os.path.expanduser("~") if d["system"] else "")
        out.append(d)
    return out


HOME = Path.home()
# Game libraries in the home folder (native and Flatpak Steam, Heroic's default)
GAME_DIRS = [HOME / ".local/share/Steam/steamapps",
             HOME / ".var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps",
             HOME / ".var/app/com.valvesoftware.Steam/data/Steam/steamapps",
             HOME / "Games"]


def _du(*paths):
    """The space the folders really take on the disk, counted together: a file linked from several places
    (ostree, Flatpak) counts once, and other drives mounted inside are skipped (-x)."""
    existing = [str(p) for p in paths if Path(p).exists()]
    if not existing:
        return 0
    try:
        r = subprocess.run(["du", "-s", "-x", "-c", "-B1", *existing], capture_output=True, text=True, timeout=900)
        return int(r.stdout.strip().splitlines()[-1].split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def space_usage():
    """What uses the space on the system disk, in plain categories (largest first).

    "System" is what is left of the used space: the system versions on the computer, logs, and other users'
    files. ostree's own folders are not measured directly: their files are linked between the versions, so a
    folder-by-folder sum would be many times the real size."""
    st = os.statvfs("/var")
    total, used = st.f_blocks * st.f_frsize, (st.f_blocks - st.f_bfree) * st.f_frsize
    home_dev = HOME.stat().st_dev
    on_home = [p for p in library.libraries() if p.exists() and p.stat().st_dev == home_dev]
    sizes = {
        "games": _du(*GAME_DIRS),
        "windows": _du(*on_home),
        "apps": max(0, _du("/var/lib/flatpak", HOME / ".local/share/flatpak", HOME / ".var/app")
                    - _du(*[p for p in GAME_DIRS if ".var/app" in str(p)])),
        "cache": _du(HOME / ".cache"),
    }
    sizes["files"] = max(0, _du(HOME) - sum(v for k, v in sizes.items() if k != "apps")
                         - _du(HOME / ".local/share/flatpak", HOME / ".var/app")
                         + _du(*[p for p in GAME_DIRS if ".var/app" in str(p)]))
    counted = sum(sizes.values())
    if counted > used:   # compressed files can be counted bigger than they are on the disk
        sizes = {k: v * used // counted for k, v in sizes.items()}
        counted = sum(sizes.values())
    sizes["system"] = used - counted
    names = {"files": tr("Your files"), "games": tr("Games"), "windows": tr("Windows programs"),
             "apps": tr("Apps"), "cache": tr("Temporary files (cache)"),
             "system": tr("System, earlier versions and other")}
    items = [{"id": k, "name": names[k], "bytes": v, "size": _size_text(v),
              "percent": 100 * v / total if total else 0}
             for k, v in sizes.items() if v > 0]
    items.sort(key=lambda i: -i["bytes"])
    return {"items": items, "free": _size_text(total - used), "total": _size_text(total)}


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
    _usage_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drives = []
        self._cleanup = ""
        self._cleanup_size = 0
        self._busy = False
        self._usage = {}
        self._usage_busy = False
        self._free_before = 0
        self._ostree = None
        self._txn = None
        self._drives_ready.connect(self._on_drives)
        self._usage_ready.connect(self._on_usage)
        self._cleanup_ready.connect(self._on_cleanup)
        # whether the machine has a Windows partition (bringing files over; we look without mounting)
        self._windows = bool(windows_import.candidates())
        self.refresh()

    drives = Property("QVariantList", lambda self: list(self._drives), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    cleanupText = Property(str, lambda self: self._cleanup, notify=changed)
    hasWindows = Property(bool, lambda self: self._windows, constant=True)
    usage = Property("QVariantMap", lambda self: dict(self._usage), notify=changed)
    usageBusy = Property(bool, lambda self: self._usage_busy, notify=changed)

    @Slot()
    def measure(self):
        """What uses the space (space_usage); it reads every file, so it runs in the background."""
        if self._usage_busy:
            return
        self._usage_busy = True
        self.changed.emit()

        def work():
            try:
                self._usage_ready.emit(space_usage())
            except OSError as e:
                log.warning("space usage: %s", e)
                self._usage_ready.emit({})
        threading.Thread(target=work, daemon=True).start()

    def _on_usage(self, usage):
        self._usage, self._usage_busy = usage, False
        self.changed.emit()

    @Slot()
    def importFromWindows(self):
        """Bringing files over from Windows: Welcome with this one step (sloth_welcome, --windows-import)."""
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

    @staticmethod
    def _free_bytes():
        st = os.statvfs("/var")
        return st.f_bavail * st.f_frsize

    @Slot()
    def cleanup(self):
        """First the system's temporary files and cached update data (rpm-ostree cleanup), then the Flatpak
        components no app uses any more. The result is the space really freed."""
        if self._busy:
            return
        self._busy = True
        self._cleanup = tr("Looking for unneeded files…")
        self._free_before = self._free_bytes()
        self.changed.emit()
        try:
            self._ostree = self._ostree or RpmOstree()
            self._ostree.cleanup(self._follow_cleanup, lambda raw: self._apps_cleanup(f"rpm-ostree: {raw}"))
        except GLib.Error as e:
            self._apps_cleanup(e.message)

    def _follow_cleanup(self, address):
        if not address:
            self._apps_cleanup()
            return
        self._txn = Transaction(address, lambda _t: None, lambda _p: None, lambda _a, _b: None,
                                lambda ok, raw: self._apps_cleanup("" if ok else raw))

    def _apps_cleanup(self, problem=""):
        """The second step (in the background): unused Flatpak components."""
        self._txn = None
        if problem:
            # e.g. no administrator approval: the apps' part still goes on
            log.warning("system cleanup: %s", problem)

        def freed_text():
            freed = self._free_bytes() - self._free_before
            if freed < 1000 ** 2:
                return tr("Nothing to clean up, everything's fine.")
            return tr("Done! {size} of space freed.", size=_size_text(freed))

        def work():
            refs = unused_flatpak_refs()
            if not refs:
                self._cleanup_ready.emit(None, freed_text())
                return
            by_inst = {}
            for inst, r in refs:
                by_inst.setdefault(inst.get_id(), (inst, []))[1].append(r.format_ref())
            try:
                for inst, names in by_inst.values():
                    txn = Flatpak.Transaction.new_for_installation(inst, None)
                    for n in names:
                        txn.add_uninstall(n)
                    txn.run(None)
                self._cleanup_ready.emit(None, freed_text())
            except GLib.Error as e:
                log.warning("cleanup: %s", e.message)
                self._cleanup_ready.emit(None, tr("Couldn't delete everything. Try again later."))

        threading.Thread(target=work, daemon=True).start()

    def _on_cleanup(self, _unused, text):
        self._busy = False
        self._cleanup = text
        self.changed.emit()
        self.refresh()
        if self._usage:
            self.measure()
