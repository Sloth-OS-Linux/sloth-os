"""Controllers (gamepads): the list of connected ones, connection and battery level.

udev marks gamepads with ID_INPUT_JOYSTICK; we read this from the
/run/udev/data database, without a password. For pairing KDE's Bluetooth settings open,
for trying the buttons KDE's Game Controller module.
"""
import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.gamepads")

INPUT = Path("/sys/class/input")
UDEV_DATA = Path("/run/udev/data")
POWER = Path("/sys/class/power_supply")
BUSES = {"0003": "usb", "0005": "bluetooth"}


def _udev_props(dev_number):
    try:
        lines = (UDEV_DATA / f"c{dev_number}").read_text(errors="replace").splitlines()
    except OSError:
        return {}
    return dict(line[2:].split("=", 1) for line in lines if line.startswith("E:") and "=" in line)


def _read(path):
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def _batteries():
    """{the HID device's real path: (percentage, whether it is charging)} for the devices' own batteries."""
    out = {}
    for ps in POWER.glob("*"):
        if _read(ps / "scope") != "Device" or not _read(ps / "capacity"):
            continue
        try:
            owner = os.path.realpath(ps / "device")
        except OSError:
            continue
        out[owner] = (int(_read(ps / "capacity") or 0), _read(ps / "status") == "Charging")
    return out


def detect():
    batteries = _batteries()
    found = {}
    for ev in sorted(INPUT.glob("event*")):
        dev_number = _read(ev / "dev")  # "13:68"
        if not dev_number or _udev_props(dev_number).get("ID_INPUT_JOYSTICK") != "1":
            continue
        device = ev / "device"
        name = _read(device / "name")
        # A controller may appear as several input devices (motion sensor, touchpad): we show it once
        hid = os.path.realpath(device / "device")
        if not name or hid in found or any(k in name.lower() for k in ("motion sensors", "touchpad")):
            continue
        battery = batteries.get(hid)
        found[hid] = {
            "name": name,
            "connection": BUSES.get(_read(device / "id/bustype"), "other"),
            "battery": battery[0] if battery else -1,
            "charging": bool(battery and battery[1]),
        }
    return sorted(found.values(), key=lambda g: g["name"].lower())


class GamepadsController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pads = []
        self.refresh()

    gamepads = Property("QVariantList", lambda self: list(self._pads), notify=changed)

    @Slot()
    def refresh(self):
        pads = detect()
        if pads != self._pads:
            self._pads = pads
            self.changed.emit()

    @Slot(str)
    def openSettings(self, kcm):
        """A KDE setting: "kcm_bluetooth" (pairing) or "kcm_gamecontroller" (testing)."""
        if kcm in ("kcm_bluetooth", "kcm_gamecontroller"):
            try:
                subprocess.Popen(["systemsettings", kcm])
            except OSError as e:
                log.warning("%s: %s", kcm, e)

    @Slot(str, result=str)
    def connectionText(self, connection):
        return {"usb": tr("With a cable"), "bluetooth": tr("Wireless (Bluetooth)")}.get(connection, tr("Connected"))
