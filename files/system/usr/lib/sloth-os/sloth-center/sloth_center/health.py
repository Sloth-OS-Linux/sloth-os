"""System health: a "What is wrong?" view in plain language.

Checks: free space, services that did not start, crashed programs,
out-of-memory, graphics card and disk errors, temperature. The system log is
read from journalctl's JSON output (the user does not see it); members of the "wheel"
group can read the whole log.
"""
import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.health")

OK, WARN, ERROR = "ok", "warning", "error"


def _journal(*args, limit=400):
    try:
        r = subprocess.run(["journalctl", "--no-pager", "-o", "json", "-b", "-n", str(limit), *args],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in r.stdout.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _msg(entry):
    m = entry.get("MESSAGE", "")
    if isinstance(m, list):  # a binary message as a list of bytes
        try:
            m = bytes(m).decode("utf-8", "replace")
        except (TypeError, ValueError):
            m = ""
    return m or ""


def check_disk():
    worst = None
    for mount in ("/var", str(Path.home())):
        try:
            st = os.statvfs(mount)
        except OSError:
            continue
        free = st.f_bavail * st.f_frsize
        pct = 100 * st.f_bavail / st.f_blocks if st.f_blocks else 100
        gb = free / 1024 ** 3
        if pct < 5 or gb < 5:
            worst = (ERROR, tr("The disk is almost full ({gb} GB free). Updates and programs may fail because of "
                               "this. Delete games or files you don't use.", gb=f"{gb:.1f}"))
        elif (pct < 12 or gb < 20) and worst is None:
            worst = (WARN, tr("The disk is getting full ({gb} GB free).", gb=f"{gb:.0f}"))
    return {"id": "disk", "title": tr("Storage"), "icon": "drive-harddisk",
            "state": worst[0] if worst else OK, "text": worst[1] if worst else tr("There's enough free space.")}


def check_failed_units():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        units = bus.call_sync("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                              "org.freedesktop.systemd1.Manager", "ListUnitsFiltered",
                              GLib.Variant("(as)", (["failed"],)), GLib.VariantType("(a(ssssssouso))"),
                              Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
    except GLib.Error as e:
        log.warning("failed units: %s", e.message)
        units = []
    names = [u[1] or u[0] for u in units]
    if not names:
        return {"id": "units", "title": tr("Services"), "icon": "preferences-system-services",
                "state": OK, "text": tr("All services started normally.")}
    return {"id": "units", "title": tr("Services"), "icon": "preferences-system-services", "state": WARN,
            "text": tr("{n} service(s) didn't start: {names}. A restart often fixes it; if not, you can restart them "
                       "on the Services page.", n=len(names),
                       names=", ".join(names[:4]) + (" …" if len(names) > 4 else "")),
            "action": "services"}


def check_crashes():
    entries = _journal("SYSLOG_IDENTIFIER=systemd-coredump", limit=100)
    apps = []
    for e in entries:
        m = re.search(r"Process \d+ \(([^)]+)\) of user", _msg(e))
        if m and m.group(1) not in apps:
            apps.append(m.group(1))
    if not apps:
        return {"id": "crash", "title": tr("Programs"), "icon": "tools-report-bug",
                "state": OK, "text": tr("No program has crashed since you turned on the computer.")}
    return {"id": "crash", "title": tr("Programs"), "icon": "tools-report-bug", "state": WARN,
            "text": tr("These programs crashed since you turned on the computer: {names}. If it happens again, try "
                       "updating them in Discover.", names=", ".join(apps[:5]))}


def check_kernel():
    """Out-of-memory, graphics card and disk errors from the kernel's messages."""
    found = {}
    for e in _journal("-k", "-p", "warning", limit=600):
        m = _msg(e)
        low = m.lower()
        if "out of memory: killed process" in low or "oom-kill" in low:
            p = re.search(r"\(([^)]+)\)", m)
            found.setdefault("oom", set()).add(p.group(1) if p else "")
        elif re.search(r"nvrm: xid|amdgpu.*(ring .* timeout|gpu reset)|i915.*gpu hang|gpu hang", low):
            found["gpu"] = True
        elif re.search(r"i/o error|medium error|uncorrectable|ata\d+.*failed command|nvme.*timeout", low):
            found["disk"] = True
    items = []
    if "oom" in found:
        names = ", ".join(sorted(n for n in found["oom"] if n)) or "?"
        items.append({"id": "oom", "title": tr("Memory"), "icon": "media-flash", "state": WARN,
                      "text": tr("The computer ran out of memory, so the system closed a program ({names}). Close "
                                 "some browser tabs or programs before playing.", names=names)})
    else:
        items.append({"id": "oom", "title": tr("Memory"), "icon": "media-flash", "state": OK,
                      "text": tr("There was no memory shortage.")})
    items.append({"id": "gpu", "title": tr("Graphics card"), "icon": "video-display",
                  "state": WARN if found.get("gpu") else OK,
                  "text": tr("The graphics card reported an error (for example, the picture froze during a game). If "
                             "it happens often, check the Drivers and hardware page, and whether the computer is "
                             "overheating.")
                  if found.get("gpu") else tr("The graphics card reported no errors.")})
    items.append({"id": "diskerr", "title": tr("Disk health"), "icon": "drive-harddisk",
                  "state": ERROR if found.get("disk") else OK,
                  "text": tr("The disk reported a read or write error. This can be a sign that the disk is failing: "
                             "copy your important files somewhere else as soon as possible!")
                  if found.get("disk") else tr("The disk reported no errors.")})
    return items


def check_temperature():
    hottest, where = 0.0, ""
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            name = (hw / "name").read_text().strip()
        except OSError:
            continue
        for t in hw.glob("temp*_input"):
            try:
                c = int(t.read_text().strip()) / 1000
            except (OSError, ValueError):
                continue
            if c > hottest and c < 150:  # above 150 the sensor is broken
                hottest, where = c, name
    part = {"k10temp": tr("Processor"), "coretemp": tr("Processor"), "amdgpu": tr("Graphics card"),
            "nvme": tr("SSD")}.get(where, tr("Component"))
    temp = f"{hottest:.0f}"
    if hottest >= 95:
        return {"id": "temp", "title": tr("Temperature"), "icon": "temperature-warm", "state": ERROR,
                "text": tr("Very hot: {part}, {temp} °C. Make sure the vents aren't blocked.",
                           part=part, temp=temp)}
    if hottest >= 85:
        return {"id": "temp", "title": tr("Temperature"), "icon": "temperature-warm", "state": WARN,
                "text": tr("Quite warm: {part}, {temp} °C. This can be normal while gaming.", part=part, temp=temp)}
    return {"id": "temp", "title": tr("Temperature"), "icon": "temperature-normal", "state": OK,
            "text": tr("The temperature is fine ({temp} °C).", temp=temp) if hottest
            else tr("No temperature data.")}


def write_log(path, lines=5000):
    """The log into a file: first the system's summary (version, image, disks), then the journal.
    "Save log" and the feedback (feedback.py) both use it."""
    with open(path, "w", encoding="utf-8") as f:
        for title, cmd in SUMMARY:
            f.write(f"===== {title}: {' '.join(cmd)}\n")
            f.flush()
            try:
                subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=20)
            except (OSError, subprocess.SubprocessError) as e:
                f.write(f"({e})\n")
            f.write("\n")
        f.write("===== Log: journalctl -b\n")
        f.flush()
        subprocess.run(["journalctl", "--no-pager", "-b", "-n", str(lines)], stdout=f,
                       stderr=subprocess.DEVNULL, timeout=60)


def run_all():
    results = [check_disk(), check_failed_units(), check_crashes(), *check_kernel(), check_temperature()]
    order = {ERROR: 0, WARN: 1, OK: 2}
    return sorted(results, key=lambda r: order[r["state"]])


# At the start of the saved log: these show which version runs and what is on the disks
SUMMARY = [
    ("System", ["cat", "/etc/os-release"]),
    ("Version", ["rpm-ostree", "status", "--booted"]),
    ("Lemezek", ["lsblk", "-o", "NAME,TYPE,SIZE,FSTYPE,LABEL,MOUNTPOINTS"]),
    ("Mounts", ["findmnt", "-o", "TARGET,SOURCE,FSTYPE,SIZE,AVAIL"]),
    ("Loop devices", ["losetup", "--list"]),
    # the source of Dolphin's Devices list (UDisks): size, name, whether hidden (HintIgnore)
    ("UDisks", ["udisksctl", "dump"]),
]

class HealthController(QObject):
    changed = Signal()
    _ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []
        self._busy = False
        self._saved = ""
        self._ready.connect(self._on_ready)
        self.check()

    results = Property("QVariantList", lambda self: list(self._results), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    savedPath = Property(str, lambda self: self._saved, notify=changed)

    @Property(str, notify=changed)
    def level(self):
        """The worst state ("ok", "warning", "error"); the interface picks the icon from it."""
        states = [r["state"] for r in self._results]
        return ERROR if ERROR in states else WARN if WARN in states else OK

    @Property(str, notify=changed)
    def summary(self):
        if self._busy and not self._results:
            return tr("Checking…")
        states = [r["state"] for r in self._results]
        if ERROR in states:
            return tr("We found something serious")
        if WARN in states:
            return tr("A few things are worth a look")
        return tr("Everything is fine")

    @Slot()
    def check(self):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()
        threading.Thread(target=lambda: self._ready.emit(run_all()), daemon=True).start()

    def _on_ready(self, results):
        self._results, self._busy = results, False
        self.changed.emit()

    @Slot(str)
    def saveLog(self, url):
        """Saves the whole log into a file (for asking for help)."""
        path = url[7:] if url.startswith("file://") else url
        try:
            write_log(path)
            self._saved = path
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("saving the log: %s", e)
            self._saved = ""
        self.changed.emit()
