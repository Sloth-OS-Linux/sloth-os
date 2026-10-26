"""Bluetooth (Drivers and hardware page): is there an adapter, is it on, which devices are connected (with battery).

Read from BlueZ over D-Bus with busctl, with a short timeout and in the background: without an adapter the
bluetooth service does not start, and asking it waits (bluetoothctl would wait for ever). Turning it on sets the
adapter's Powered property, as KDE's Bluetooth applet does (no password for the signed-in user). Pairing is left to
KDE's Bluetooth settings.
"""
import json
import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

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


def read(run=_run):
    return parse(run(BUS + ["call", "org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"]))


class BluetoothController(QObject):
    changed = Signal()
    _loaded = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = parse("")
        self._checked = False
        self._loaded.connect(self._on_loaded)
        # read when the Drivers and hardware page opens (not at every start of Sloth Center)

    checked = Property(bool, lambda self: self._checked, notify=changed)
    adapter = Property(bool, lambda self: self._data["adapter"], notify=changed)
    powered = Property(bool, lambda self: self._data["powered"], notify=changed)
    devices = Property("QVariantList", lambda self: list(self._data["devices"]), notify=changed)

    @Slot()
    def refresh(self):
        threading.Thread(target=lambda: self._loaded.emit(read()), daemon=True).start()

    def _on_loaded(self, data):
        self._data, self._checked = data, True
        self.changed.emit()

    @Slot()
    def turnOn(self):
        path = self._data["adapterPath"]
        if path:
            _run(BUS + ["set-property", "org.bluez", path, "org.bluez.Adapter1", "Powered", "b", "true"])
        self.refresh()

    @Slot()
    def openSettings(self):
        try:
            subprocess.Popen(["systemsettings", "kcm_bluetooth"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("System Settings: %s", e)
