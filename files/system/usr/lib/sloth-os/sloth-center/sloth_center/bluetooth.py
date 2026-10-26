"""Bluetooth (Drivers and hardware page): is there an adapter, is it on, which devices are connected (with battery).

Read from BlueZ over D-Bus with busctl, with a short timeout and in the background: without an adapter the
bluetooth service does not start, and asking it waits (bluetoothctl would wait for ever). KDE's Bluetooth applet
turns it off with an rfkill block, and a blocked adapter refuses Powered: turning it on first lifts the block (the
signed-in user may, /dev/rfkill is theirs), then sets Powered. No password. Pairing is left to KDE's Bluetooth
settings.
"""
import json
import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.bluetooth")

BUS = ["busctl", "--system", "--timeout=3", "--json=short"]


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return ""


def _value(props, key, default=None):
    v = props.get(key)
    return v.get("data", default) if isinstance(v, dict) else default


def parse(text):
    """busctl's JSON of BlueZ's GetManagedObjects -> {adapter, adapterPath, powered, devices: [{name, icon, battery}]}
    (only the connected devices; battery -1 if not known)."""
    result = {"adapter": False, "adapterPath": "", "powered": False, "devices": []}
    try:
        objects = json.loads(text)["data"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return result
    for path, interfaces in sorted(objects.items()):
        adapter = interfaces.get("org.bluez.Adapter1")
        if adapter and not result["adapter"]:
            result.update(adapter=True, adapterPath=path, powered=bool(_value(adapter, "Powered", False)))
        device = interfaces.get("org.bluez.Device1")
        if device and _value(device, "Connected", False):
            battery = interfaces.get("org.bluez.Battery1")
            result["devices"].append({
                "name": _value(device, "Alias") or _value(device, "Name") or _value(device, "Address", ""),
                "icon": _value(device, "Icon") or "preferences-system-bluetooth",
                "battery": int(_value(battery, "Percentage", -1)) if battery else -1,
            })
    return result


def blocked(run=_run):
    """Whether Bluetooth is turned off with an rfkill block (KDE's applet, an airplane-mode key)."""
    for line in run(["rfkill", "-n", "-o", "TYPE,SOFT,HARD"]).splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "bluetooth" and "blocked" in parts[1:]:
            return True
    return False


def read(run=_run):
    result = parse(run(BUS + ["call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"]))
    # a blocked adapter can still report Powered for a moment: the block is what KDE's applet shows
    if result["adapter"] and blocked(run):
        result["powered"] = False
        result["devices"] = []
    return result


class BluetoothController(QObject):
    changed = Signal()
    _loaded = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = parse("")
        self._checked = False
        self._error = ""
        self._turning_on = False
        self._loaded.connect(self._on_loaded)
        # read when the Drivers and hardware page opens (not at every start of Sloth Center)

    checked = Property(bool, lambda self: self._checked, notify=changed)
    adapter = Property(bool, lambda self: self._data["adapter"], notify=changed)
    powered = Property(bool, lambda self: self._data["powered"], notify=changed)
    devices = Property("QVariantList", lambda self: list(self._data["devices"]), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)

    @Slot()
    def refresh(self):
        threading.Thread(target=lambda: self._loaded.emit(read()), daemon=True).start()

    def _on_loaded(self, data):
        self._data, self._checked = data, True
        if self._turning_on:
            self._turning_on = False
            self._error = "" if data["powered"] else tr("Couldn't turn on Bluetooth.")
        self.changed.emit()

    @Slot()
    def turnOn(self):
        self._error = ""
        # the block of KDE's applet (or of an airplane-mode key) first, then the adapter itself
        _run(["rfkill", "unblock", "bluetooth"])
        path = self._data["adapterPath"]
        if path:
            _run(BUS + ["set-property", "org.bluez", path, "org.bluez.Adapter1", "Powered", "b", "true"])
        # the adapter needs a moment after the block is lifted
        self._turning_on = True
        QTimer.singleShot(1500, self.refresh)

    @Slot()
    def openSettings(self):
        try:
            subprocess.Popen(["systemsettings", "kcm_bluetooth"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("System Settings: %s", e)
