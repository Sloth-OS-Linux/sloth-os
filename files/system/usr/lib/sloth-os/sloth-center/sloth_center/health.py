"""Rendszer egészség: "Mi a baj?" nézet emberi nyelven.

Ellenőrzések: szabad hely, el nem indult szolgáltatások, összeomlott programok,
memóriahiány, videókártya- és lemezhibák, hőmérséklet. A rendszernaplót a
journalctl JSON kimenetéből olvassuk (a felhasználó nem látja), a "wheel"
csoport tagjai olvashatják a teljes naplót.
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
    if isinstance(m, list):  # bináris üzenet bájtlistaként
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
            worst = (ERROR, tr("Szinte elfogyott a hely a lemezen ({gb} GB szabad). Emiatt a frissítések és a "
                               "programok hibázhatnak. Törölj nem használt játékokat vagy fájlokat.", gb=f"{gb:.1f}"))
        elif (pct < 12 or gb < 20) and worst is None:
            worst = (WARN, tr("Kezd fogyni a hely a lemezen ({gb} GB szabad).", gb=f"{gb:.0f}"))
    return {"id": "disk", "title": tr("Tárhely"), "icon": "drive-harddisk",
            "state": worst[0] if worst else OK, "text": worst[1] if worst else tr("Van elég szabad hely.")}


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
        return {"id": "units", "title": tr("Szolgáltatások"), "icon": "preferences-system-services",
                "state": OK, "text": tr("Minden szolgáltatás rendben elindult.")}
    return {"id": "units", "title": tr("Szolgáltatások"), "icon": "preferences-system-services", "state": WARN,
            "text": tr("{n} szolgáltatás nem indult el: {names}. Sokszor egy újraindítás megoldja; ha nem, "
                       "a Szolgáltatások oldalon újraindíthatod.", n=len(names),
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
        return {"id": "crash", "title": tr("Programok"), "icon": "tools-report-bug",
                "state": OK, "text": tr("Mióta bekapcsoltad a gépet, egy program sem omlott össze.")}
    return {"id": "crash", "title": tr("Programok"), "icon": "tools-report-bug", "state": WARN,
            "text": tr("Ezek a programok összeomlottak, mióta bekapcsoltad a gépet: {names}. Ha újra előfordul, "
                       "próbáld meg frissíteni őket a Discoverben.", names=", ".join(apps[:5]))}


def check_kernel():
    """Memóriahiány, videókártya- és lemezhibák a kernel üzeneteiből."""
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
        items.append({"id": "oom", "title": tr("Memória"), "icon": "media-flash", "state": WARN,
                      "text": tr("Elfogyott a memória, ezért a rendszer bezárt egy programot ({names}). "
                                 "Zárj be néhány böngészőfület vagy programot, mielőtt játszol.", names=names)})
    else:
        items.append({"id": "oom", "title": tr("Memória"), "icon": "media-flash", "state": OK,
                      "text": tr("Nem volt memóriahiány.")})
    items.append({"id": "gpu", "title": tr("Videókártya"), "icon": "video-display",
                  "state": WARN if found.get("gpu") else OK,
                  "text": tr("A videókártya hibát jelzett (például egy játék közben lefagyott a kép). Ha gyakran "
                             "előfordul, nézd meg a Driverek és hardver oldalt, és hogy nem melegszik-e túl a gép.")
                  if found.get("gpu") else tr("A videókártya nem jelzett hibát.")})
    items.append({"id": "diskerr", "title": tr("Lemez állapota"), "icon": "drive-harddisk",
                  "state": ERROR if found.get("disk") else OK,
                  "text": tr("A lemez olvasási vagy írási hibát jelzett. Ez a lemez meghibásodásának jele lehet: "
                             "mentsd el minél előbb a fontos fájljaidat egy másik helyre!")
                  if found.get("disk") else tr("A lemez nem jelzett hibát.")})
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
            if c > hottest and c < 150:  # 150 felett hibás érzékelő
                hottest, where = c, name
    part = {"k10temp": tr("Processzor"), "coretemp": tr("Processzor"), "amdgpu": tr("Videókártya"),
            "nvme": tr("SSD")}.get(where, tr("Alkatrész"))
    temp = f"{hottest:.0f}"
    if hottest >= 95:
        return {"id": "temp", "title": tr("Hőmérséklet"), "icon": "temperature-warm", "state": ERROR,
                "text": tr("Nagyon meleg: {part}, {temp} °C. Ellenőrizd, hogy a szellőzők nincsenek-e eltakarva.",
                           part=part, temp=temp)}
    if hottest >= 85:
        return {"id": "temp", "title": tr("Hőmérséklet"), "icon": "temperature-warm", "state": WARN,
                "text": tr("Elég meleg: {part}, {temp} °C. Játék közben ez normális lehet.", part=part, temp=temp)}
    return {"id": "temp", "title": tr("Hőmérséklet"), "icon": "temperature-normal", "state": OK,
            "text": tr("A hőmérséklet rendben van ({temp} °C).", temp=temp) if hottest
            else tr("Nincs hőmérséklet-adat.")}


def run_all():
    results = [check_disk(), check_failed_units(), check_crashes(), *check_kernel(), check_temperature()]
    order = {ERROR: 0, WARN: 1, OK: 2}
    return sorted(results, key=lambda r: order[r["state"]])


# A mentett napló elejére: ezekből látszik, melyik változat fut, és mi van a lemezeken
SUMMARY = [
    ("Rendszer", ["cat", "/etc/os-release"]),
    ("Változat", ["rpm-ostree", "status", "--booted"]),
    ("Lemezek", ["lsblk", "-o", "NAME,TYPE,SIZE,FSTYPE,LABEL,MOUNTPOINTS"]),
    ("Csatolások", ["findmnt", "-o", "TARGET,SOURCE,FSTYPE,SIZE,AVAIL"]),
    ("Loop eszközök", ["losetup", "--list"]),
    # a Dolphin Eszközök listájának forrása (UDisks): méret, név, rejtett-e (HintIgnore)
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
        """A legrosszabb állapot ("ok", "warning", "error"); a felület ehhez választ ikont."""
        states = [r["state"] for r in self._results]
        return ERROR if ERROR in states else WARN if WARN in states else OK

    @Property(str, notify=changed)
    def summary(self):
        if self._busy and not self._results:
            return tr("Ellenőrzés…")
        states = [r["state"] for r in self._results]
        if ERROR in states:
            return tr("Valami komoly gondot találtunk")
        if WARN in states:
            return tr("Pár dologra érdemes figyelni")
        return tr("Minden rendben van")

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
        """A teljes napló mentése egy fájlba (segítségkéréshez)."""
        path = url[7:] if url.startswith("file://") else url
        try:
            with open(path, "w", encoding="utf-8") as f:
                # Előbb a rendszer összefoglalója (verzió, image, lemezek), utána a napló
                for title, cmd in SUMMARY:
                    f.write(f"===== {title}: {' '.join(cmd)}\n")
                    f.flush()
                    try:
                        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=20)
                    except (OSError, subprocess.SubprocessError) as e:
                        f.write(f"({e})\n")
                    f.write("\n")
                f.write("===== Napló: journalctl -b\n")
                f.flush()
                subprocess.run(["journalctl", "--no-pager", "-b", "-n", "5000"], stdout=f,
                               stderr=subprocess.DEVNULL, timeout=60)
            self._saved = path
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("napló mentése: %s", e)
            self._saved = ""
        self.changed.emit()
