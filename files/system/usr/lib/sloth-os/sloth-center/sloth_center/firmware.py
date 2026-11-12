"""The computer's firmware (BIOS/UEFI, and the firmware of disks, docks…): Sloth Center → Updates.

fwupd does the work (Fedora's fwupd 2.x, its fwupdmgr client in JSON mode); the firmware comes from the LVFS
(Linux Vendor Firmware Service), uploaded and signed by the makers themselves. Safety comes first:

  - only the stable LVFS remote is used (lvfs-testing stays off, as Fedora ships it), and only releases fwupd marks
    "trusted-payload" (signed) and "is-upgrade" are offered: never an older or unsigned one;
  - nothing is installed by itself: the user presses Install and confirms it;
  - our own checks before it: a laptop must be plugged in and at 30% or more; fwupd checks it again itself (its
    device problems "require-ac-power", "system-power-too-low", "lid-is-closed"… are shown in plain words and the
    update can't be started then);
  - when Windows with BitLocker is on the machine, or fwupd says the update affects disk encryption
    ("affects-fde": Windows may ask for its BitLocker recovery key once after it), the user has to confirm that they
    have the recovery key;
  - a BIOS update is written at the next restart (UEFI capsule): the page says so and offers the restart.

Checking (fwupdmgr refresh) and installing a signed update need no password (fwupd's polkit policy:
org.freedesktop.fwupd.refresh-remote and update-internal-trusted are "yes" for the active user); anything else asks
through KDE's password window.
"""
import json
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import N_, tr

log = logging.getLogger("sloth-center.firmware")

FWUPDMGR = "fwupdmgr"
QUIET = ["--json", "--no-unreported-check", "--no-metadata-check", "--no-remote-check", "--no-security-fix"]
REMOTES = {"lvfs", "vendor-directory"}   # stable LVFS, or firmware the maker put on the machine
MIN_BATTERY = 30
POWER_SUPPLY = Path("/sys/class/power_supply")

# fwupd's device problems -> what the user can do about it
PROBLEMS = {
    "require-ac-power": N_("Plug in the charger first."),
    "system-power-too-low": N_("Charge the battery a little first."),
    "lid-is-closed": N_("Open the laptop's lid first."),
    "update-in-progress": N_("Another update is running. Wait for it to finish."),
    "update-pending": N_("An update is waiting for a restart. Restart the computer first."),
    "in-use": N_("The device is in use. Close what uses it, then try again."),
    "unreachable": N_("The device can't be reached right now. Check that it's connected."),
    "missing-license": N_("The maker needs a license for this update."),
}


def _run(args, timeout):
    return subprocess.run([FWUPDMGR] + args, capture_output=True, text=True, timeout=timeout)


def _text(markup):
    """The release notes come as simple XML markup (<p>, <li>): plain text with bullets."""
    text = re.sub(r"<li>", "• ", markup or "")
    text = re.sub(r"</(p|li|ul|ol)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def power():
    """{"battery": bool, "ac": bool, "percent": int|None} from the kernel's power supply list (the computer's own
    batteries only: a wireless mouse's battery has scope "Device")."""
    ac, batteries = False, []
    try:
        supplies = list(POWER_SUPPLY.iterdir())
    except OSError:
        supplies = []
    for s in supplies:
        try:
            kind = (s / "type").read_text().strip()
            if kind == "Mains" and (s / "online").read_text().strip() == "1":
                ac = True
            elif kind == "Battery":
                scope = (s / "scope").read_text().strip().lower() if (s / "scope").exists() else "system"
                if scope != "device":
                    batteries.append(int((s / "capacity").read_text().strip()))
        except (OSError, ValueError):
            continue
    return {"battery": bool(batteries), "ac": ac or not batteries,
            "percent": min(batteries) if batteries else None}


def bitlocker_on_machine():
    """Whether a BitLocker-locked partition is on the machine (Windows with BitLocker next to Sloth OS)."""
    try:
        out = subprocess.run(["lsblk", "-J", "-o", "FSTYPE"], capture_output=True, text=True, timeout=10).stdout
        devices = json.loads(out).get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return False

    def walk(nodes):
        return any((n.get("fstype") or "") == "BitLocker" or walk(n.get("children") or []) for n in nodes)
    return walk(devices)


def parse_updates(data):
    """fwupdmgr get-updates --json -> [{id, name, vendor, current, version, summary, notes, urgency, problems,
    reboot, fde, ac}]: the newest safe release of each device."""
    out = []
    for d in data.get("Devices", []):
        flags = set(d.get("Flags", []))
        releases = [r for r in d.get("Releases", [])
                    if {"trusted-payload", "is-upgrade"} <= set(r.get("Flags", []))
                    and r.get("RemoteId", "lvfs") in REMOTES]
        if not releases or "updatable" not in flags:     # "updatable-hidden": only after a restart
            continue
        r = releases[0]     # fwupd lists the newest first
        out.append({
            "id": d.get("DeviceId", ""), "name": d.get("Name", ""), "vendor": d.get("Vendor", ""),
            "current": d.get("Version", ""), "version": r.get("Version", ""),
            "summary": r.get("Summary", ""), "notes": _text(r.get("Description", "")),
            "urgency": r.get("Urgency", ""), "problems": [p for p in d.get("Problems", []) if p in PROBLEMS],
            "reboot": "needs-reboot" in flags or "needs-shutdown" in flags,
            "fde": "affects-fde" in flags, "ac": "require-ac" in flags,
        })
    return [u for u in out if u["id"]]


class FirmwareController(QObject):
    changed = Signal()
    _done = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "idle"     # idle | checking | ready | installing | restart | failed
        self._updates = []
        self._message = ""
        self._bitlocker = None
        self._done.connect(self._on_done)

    @Property(str, notify=changed)
    def state(self):
        return self._state

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(bool, constant=True)
    def available(self):
        return shutil.which(FWUPDMGR) is not None

    @Property("QVariantList", notify=changed)
    def updates(self):
        p = power()
        out = []
        for u in self._updates:
            blockers = [tr(PROBLEMS[x]) for x in u["problems"]]
            if p["battery"] and not p["ac"]:
                blockers.append(tr(PROBLEMS["require-ac-power"]))
            elif p["battery"] and p["percent"] is not None and p["percent"] < MIN_BATTERY:
                blockers.append(tr("Let the battery charge to at least {percent}% first.", percent=MIN_BATTERY))
            out.append({**u, "blockers": list(dict.fromkeys(blockers)),
                        "recoveryKey": u["fde"] or bool(self._bitlocker),
                        "urgent": u["urgency"] in ("high", "critical")})
        return out

    def _work(self, kind, fn):
        def run():
            try:
                result = fn()
            except Exception as e:  # noqa: BLE001 – the page must leave "checking"/"installing"
                log.warning("firmware %s: %s", kind, e)
                result = e
            self._done.emit(kind, result)
        threading.Thread(target=run, daemon=True).start()

    @Slot()
    def check(self):
        if self._state in ("checking", "installing"):
            return
        self._state, self._message = "checking", ""
        self.changed.emit()

        def fn():
            if self._bitlocker is None:
                self._bitlocker = bitlocker_on_machine()
            # the list of firmware from the LVFS (no password; offline the last list is used)
            refresh = _run(["refresh", "--force"] + QUIET, 300)
            if refresh.returncode not in (0, 2):
                log.info("fwupdmgr refresh: %s", (refresh.stderr or refresh.stdout).strip()[:500])
            got = _run(["get-updates"] + QUIET, 120)
            if got.returncode not in (0, 2) and not got.stdout.strip().startswith("{"):
                log.info("fwupdmgr get-updates: %s", (got.stderr or got.stdout).strip()[:500])
                return []
            try:
                return parse_updates(json.loads(got.stdout or "{}"))
            except ValueError:
                return []
        self._work("check", fn)

    @Slot(str)
    def install(self, device_id):
        u = next((x for x in self.updates if x["id"] == device_id), None)
        if not u or u["blockers"] or self._state != "ready":
            return
        self._state, self._message = "installing", ""
        self.changed.emit()

        def fn():
            res = _run(["update", device_id, "--assume-yes", "--no-reboot-check"] + QUIET, 3600)
            return {"ok": res.returncode == 0, "reboot": u["reboot"],
                    "error": (res.stderr or res.stdout).strip()[:2000]}
        self._work("install", fn)

    def _on_done(self, kind, result):
        if isinstance(result, Exception):
            self._state = "failed"
            self._message = tr("Something went wrong. Try again later.")
        elif kind == "check":
            self._updates = result
            self._state = "ready"
            self._message = "" if result else tr("The computer's firmware is up to date.")
        elif result["ok"]:
            self._updates = []
            self._state = "restart" if result["reboot"] else "ready"
            self._message = tr("Restart the computer to finish. The update is written while it starts: that can "
                               "take a few minutes and the screen may go dark. Don't turn the computer off.") \
                if result["reboot"] else tr("The firmware update is installed.")
        else:
            log.warning("fwupdmgr update: %s", result["error"])
            self._state = "failed"
            low = result["error"].lower()
            self._message = tr(PROBLEMS["require-ac-power"]) if "ac power" in low else \
                tr(PROBLEMS["system-power-too-low"]) if "battery" in low else \
                tr("The update couldn't be installed. Try again later; if it keeps happening, send a report from "
                   "Feedback.")
        self.changed.emit()
