"""Printers and scanners (Sloth Center → Printers and scanners): what Windows has under Settings → Bluetooth & devices
→ Printers & scanners, in plain words.

Most printers of the last ten years need no driver (IPP Everywhere / AirPrint): CUPS with cups-browsed and ipp-usb
shows the ones on the network and on USB by themselves (lpstat -e lists them, also the "temporary" ones CUPS makes
when they are first used). This page lists them, prints a test page, sets the one used by default (lpoptions -d: for
this user, no password) and opens the print queue (plasma-print-queue) or KDE's printer settings for adding one by
hand (systemsettings kcm_printer_manager). Scanners: SANE (scanimage -L; network scanners through sane-airscan),
scanning in Skanpage.
"""
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.printers")

C_ENV = {**os.environ, "LC_ALL": "C"}
TEST_PAGE = "/usr/share/cups/data/default-testpage.pdf"
USER_LPOPTIONS = Path.home() / ".cups" / "lpoptions"


def _run(args, timeout=20):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=C_ENV)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def default_printer():
    """The user's own default (lpoptions -d writes it into ~/.cups/lpoptions), or the system's."""
    try:
        for line in USER_LPOPTIONS.read_text().splitlines():
            if line.startswith("Default "):
                return line.split()[1]
    except (OSError, IndexError):
        pass
    m = re.search(r"system default destination: (\S+)", _run(["lpstat", "-d"]))
    return m.group(1) if m else ""


def parse_lpstat(names_text, details_text):
    """lpstat -e (every destination) and lpstat -l -p (the made ones, with state and description) ->
    [{name, label, state}]; state: "idle" | "printing" | "stopped" | "" (not used yet: made at the first print)."""
    details, current = {}, None
    for line in details_text.splitlines():
        m = re.match(r"printer (\S+) (?:is idle|now printing|disabled)", line)
        if m:
            current = m.group(1)
            state = "printing" if "now printing" in line else "stopped" if "disabled" in line else "idle"
            details[current] = {"state": state, "label": ""}
        elif current and line.strip().startswith("Description:"):
            details[current]["label"] = line.split(":", 1)[1].strip()
    out = []
    for name in [n.strip() for n in names_text.splitlines() if n.strip()]:
        d = details.get(name, {"state": "", "label": ""})
        out.append({"name": name, "label": d["label"] or name.replace("_", " "), "state": d["state"]})
    return out


def parse_scanners(text):
    """scanimage -f '%d\\t%v %m%n' -> [{device, label}] (the cameras SANE lists too are left out)."""
    out = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        device, label = line.split("\t", 1)
        if device.startswith(("v4l:", "video")):
            continue
        out.append({"device": device, "label": label.strip() or device})
    return out


class PrintersController(QObject):
    changed = Signal()
    _found = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._printers, self._scanners = [], []
        self._default = ""
        self._busy = False
        self._message = ""
        self._found.connect(self._on_found)

    @Property("QVariantList", notify=changed)
    def printers(self):
        return [{**p, "isDefault": p["name"] == self._default,
                 "stateText": {"idle": tr("Ready"), "printing": tr("Printing"),
                               "stopped": tr("Stopped")}.get(p["state"], tr("Ready when you print"))}
                for p in self._printers]

    @Property("QVariantList", notify=changed)
    def scanners(self):
        return self._scanners

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Slot()
    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()

        def work():
            printers = parse_lpstat(_run(["lpstat", "-e"]), _run(["lpstat", "-l", "-p"]))
            # scanners on the network answer slowly: up to half a minute
            scanners = parse_scanners(_run(["scanimage", "-f", "%d\t%v %m%n"], timeout=40))
            self._found.emit({"printers": printers, "scanners": scanners, "default": default_printer()})
        threading.Thread(target=work, daemon=True).start()

    def _on_found(self, data):
        self._printers, self._scanners, self._default = data["printers"], data["scanners"], data["default"]
        self._busy = False
        self.changed.emit()

    @Slot(str)
    def printTestPage(self, name):
        r = subprocess.run(["lp", "-d", name, "-t", "Sloth OS", TEST_PAGE], capture_output=True, text=True,
                           env=C_ENV)
        ok = r.returncode == 0
        if not ok:
            log.warning("lp %s: %s", name, r.stderr.strip())
        self._message = tr("The test page is on its way to the printer.") if ok else \
            tr("The test page couldn't be sent. Check that the printer is on and connected.")
        self.changed.emit()

    @Slot(str)
    def setDefault(self, name):
        if subprocess.run(["lpoptions", "-d", name], capture_output=True, env=C_ENV).returncode == 0:
            self._default = name
            self._message = ""
        self.changed.emit()

    def _open(self, args):
        try:
            subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("%s: %s", args[0], e)

    @Slot(str)
    def openQueue(self, name):
        self._open(["plasma-print-queue", name])

    @Slot()
    def addPrinter(self):
        self._open(["systemsettings", "kcm_printer_manager"])

    @Slot()
    def scan(self):
        self._open(["skanpage"])
