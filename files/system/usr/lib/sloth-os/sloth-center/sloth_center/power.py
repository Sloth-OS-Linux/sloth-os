"""Power and battery (Sloth Center → Power and battery): what Windows has under Settings → System → Power & battery.

  - the battery (UPower): the charge, charging or not, the time left, and its health (how much it holds compared
    with when it was new); only on computers with a battery;
  - the power mode (power-profiles-daemon's D-Bus interface, tuned-ppd on Fedora): power saver, balanced,
    performance; the same switch as the quick settings;
  - when the screen turns off and when the computer goes to sleep, plugged in and on battery, and what closing the
    lid and pressing the power button do: KDE's power management (powerdevilrc, which KDE's Energy Saving settings
    show the same way), read again by PowerDevil at once.
Nothing here needs a password. A choice the user never made shows as "As KDE sets it" (PowerDevil's own default).
"""
import logging
import subprocess

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from .accessibility import read, write
from . import kde_settings

log = logging.getLogger("sloth-center.power")

UPOWER = "org.freedesktop.UPower"
PROFILES = ("net.hadess.PowerProfiles", "/net/hadess/PowerProfiles", "net.hadess.PowerProfiles")
PROFILE_ORDER = ("power-saver", "balanced", "performance")
# minutes; 0: never, -1: not set (PowerDevil's default)
SCREEN_CHOICES = (-1, 2, 5, 10, 15, 30, 0)
SLEEP_CHOICES = (-1, 10, 15, 30, 60, 120, 0)
# PowerDevil's actions (PowerButtonAction / LidAction values)
NOTHING, SLEEP, SHUTDOWN, ASK, TURN_OFF_SCREEN = 0, 1, 8, 16, 64
LID_CHOICES = (SLEEP, TURN_OFF_SCREEN, NOTHING)
BUTTON_CHOICES = (ASK, SLEEP, SHUTDOWN)
SOURCES = ("AC", "Battery")


def _bus():
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def _props(bus, name, path, iface):
    try:
        return bus.call_sync(name, path, "org.freedesktop.DBus.Properties", "GetAll", GLib.Variant("(s)", (iface,)),
                             GLib.VariantType("(a{sv})"), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    except GLib.Error as e:
        log.info("%s: %s", path, e.message)
        return {}


def battery():
    """{"present", "percent", "charging", "minutes", "health"} of the batteries together, or present=False."""
    bus = _bus()
    display = _props(bus, UPOWER, "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device")
    if not display.get("IsPresent") or display.get("Type") != 2:  # 2: a battery
        return {"present": False}
    state = display.get("State", 0)  # 1: charging, 2: discharging, 4: fully charged
    seconds = display.get("TimeToFull", 0) if state == 1 else display.get("TimeToEmpty", 0)
    full = design = 0.0
    try:
        paths = bus.call_sync(UPOWER, "/org/freedesktop/UPower", UPOWER, "EnumerateDevices", None,
                              GLib.VariantType("(ao)"), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    except GLib.Error:
        paths = []
    for path in paths:
        dev = _props(bus, UPOWER, path, "org.freedesktop.UPower.Device")
        if dev.get("Type") == 2 and dev.get("PowerSupply"):
            full += dev.get("EnergyFull", 0.0)
            design += dev.get("EnergyFullDesign", 0.0)
    health = round(100 * full / design) if design > 0 and full > 0 else -1
    return {"present": True, "percent": round(display.get("Percentage", 0)), "charging": state in (1, 4),
            "full": state == 4, "minutes": int(seconds // 60), "health": min(health, 100)}


def lid_present():
    props = _props(_bus(), UPOWER, "/org/freedesktop/UPower", UPOWER)
    return bool(props.get("LidIsPresent"))


def profiles():
    """(the available power modes in order, the active one); ([], "") without power-profiles-daemon."""
    props = _props(_bus(), PROFILES[0], PROFILES[1], PROFILES[2])
    names = {p.get("Profile") for p in props.get("Profiles", [])}
    return [p for p in PROFILE_ORDER if p in names], props.get("ActiveProfile", "")


def set_profile(name):
    try:
        _bus().call_sync(PROFILES[0], PROFILES[1], "org.freedesktop.DBus.Properties", "Set",
                         GLib.Variant("(ssv)", (PROFILES[2], "ActiveProfile", GLib.Variant("s", name))), None,
                         Gio.DBusCallFlags.NONE, 10000, None)
    except GLib.Error as e:
        log.warning("power mode %s: %s", name, e.message)


def _minutes(source, group, on_key, sec_key, action_key=None):
    """The minutes in powerdevilrc, 0 for never, -1 when the user never chose."""
    if action_key:
        action = read("powerdevilrc", f"{source}][{group}", action_key, "")
        if action == "":
            return -1
        if action == "0":
            return 0
    else:
        on = read("powerdevilrc", f"{source}][{group}", on_key, "")
        if on == "":
            return -1
        if on == "false":
            return 0
    try:
        return max(1, int(read("powerdevilrc", f"{source}][{group}", sec_key, "0")) // 60)
    except ValueError:
        return -1


def screen_off(source):
    return _minutes(source, "Display", "TurnOffDisplayWhenIdle", "TurnOffDisplayIdleTimeoutSec")


def set_screen_off(source, minutes):
    group = f"{source}][Display"
    if minutes < 0:
        write("powerdevilrc", group, "TurnOffDisplayWhenIdle")
        write("powerdevilrc", group, "TurnOffDisplayIdleTimeoutSec")
    else:
        write("powerdevilrc", group, "TurnOffDisplayWhenIdle", "true" if minutes else "false", "bool")
        if minutes:
            write("powerdevilrc", group, "TurnOffDisplayIdleTimeoutSec", minutes * 60, "int")


def sleep_after(source):
    return _minutes(source, "SuspendAndShutdown", None, "AutoSuspendIdleTimeoutSec", "AutoSuspendAction")


def set_sleep_after(source, minutes):
    group = f"{source}][SuspendAndShutdown"
    if minutes < 0:
        write("powerdevilrc", group, "AutoSuspendAction")
        write("powerdevilrc", group, "AutoSuspendIdleTimeoutSec")
    else:
        write("powerdevilrc", group, "AutoSuspendAction", SLEEP if minutes else NOTHING, "int")
        if minutes:
            write("powerdevilrc", group, "AutoSuspendIdleTimeoutSec", minutes * 60, "int")


def action(key, choices, default):
    try:
        value = int(read("powerdevilrc", "AC][SuspendAndShutdown", key, str(default)))
    except ValueError:
        value = default
    return value if value in choices else default


def set_action(key, value):
    # the same everywhere: plugged in, on battery and on low battery
    for source in ("AC", "Battery", "LowBattery"):
        write("powerdevilrc", f"{source}][SuspendAndShutdown", key, value, "int")


def reload_powerdevil():
    for method in ("reparseConfiguration", "refreshStatus"):
        subprocess.run(["dbus-send", "--session", "--type=method_call", "--dest=org.kde.Solid.PowerManagement",
                        "/org/kde/Solid/PowerManagement", f"org.kde.Solid.PowerManagement.{method}"],
                       capture_output=True, timeout=10)


class PowerController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._battery = {"present": False}
        self._profiles, self._profile = [], ""
        self._lid = False
        self._screen = {s: -1 for s in SOURCES}
        self._sleep = {s: -1 for s in SOURCES}
        self._lid_action, self._button = SLEEP, ASK
        self._timer = QTimer(self)
        self._timer.setInterval(30000)
        self._timer.timeout.connect(self.refreshBattery)
        self.refresh()

    hasBattery = Property(bool, lambda self: self._battery.get("present", False), notify=changed)
    batteryPercent = Property(int, lambda self: self._battery.get("percent", 0), notify=changed)
    charging = Property(bool, lambda self: self._battery.get("charging", False), notify=changed)
    fullyCharged = Property(bool, lambda self: self._battery.get("full", False), notify=changed)
    minutesLeft = Property(int, lambda self: self._battery.get("minutes", 0), notify=changed)
    batteryHealth = Property(int, lambda self: self._battery.get("health", -1), notify=changed)
    hasLid = Property(bool, lambda self: self._lid, notify=changed)
    powerModes = Property("QVariantList", lambda self: list(self._profiles), notify=changed)
    powerMode = Property(str, lambda self: self._profile, notify=changed)
    screenChoices = Property("QVariantList", lambda self: list(SCREEN_CHOICES), constant=True)
    sleepChoices = Property("QVariantList", lambda self: list(SLEEP_CHOICES), constant=True)
    lidChoices = Property("QVariantList", lambda self: list(LID_CHOICES), constant=True)
    buttonChoices = Property("QVariantList", lambda self: list(BUTTON_CHOICES), constant=True)
    screenOffAc = Property(int, lambda self: self._screen["AC"], notify=changed)
    screenOffBattery = Property(int, lambda self: self._screen["Battery"], notify=changed)
    sleepAc = Property(int, lambda self: self._sleep["AC"], notify=changed)
    sleepBattery = Property(int, lambda self: self._sleep["Battery"], notify=changed)
    lidAction = Property(int, lambda self: self._lid_action, notify=changed)
    buttonAction = Property(int, lambda self: self._button, notify=changed)

    @Slot()
    def refresh(self):
        try:
            self._battery = battery()
            self._lid = lid_present()
            self._profiles, self._profile = profiles()
        except GLib.Error as e:
            log.warning("power: %s", e.message)
        for source in SOURCES:
            self._screen[source] = screen_off(source)
            self._sleep[source] = sleep_after(source)
        self._lid_action = action("LidAction", LID_CHOICES, SLEEP)
        self._button = action("PowerButtonAction", BUTTON_CHOICES, ASK)
        if self._battery.get("present") and not self._timer.isActive():
            self._timer.start()
        self.changed.emit()

    @Slot()
    def refreshBattery(self):
        self._battery = battery()
        self._profiles, self._profile = profiles()
        self.changed.emit()

    @Slot(str)
    def setPowerMode(self, name):
        if name in self._profiles:
            set_profile(name)
        self.refreshBattery()

    @Slot(str, int)
    def setScreenOff(self, source, minutes):
        if source in SOURCES and minutes in SCREEN_CHOICES:
            set_screen_off(source, minutes)
            reload_powerdevil()
        self.refresh()

    @Slot(str, int)
    def setSleepAfter(self, source, minutes):
        if source in SOURCES and minutes in SLEEP_CHOICES:
            set_sleep_after(source, minutes)
            reload_powerdevil()
        self.refresh()

    @Slot(int)
    def setLidAction(self, value):
        if value in LID_CHOICES:
            set_action("LidAction", value)
            reload_powerdevil()
        self.refresh()

    @Slot(int)
    def setButtonAction(self, value):
        if value in BUTTON_CHOICES:
            set_action("PowerButtonAction", value)
            reload_powerdevil()
        self.refresh()

    @Slot()
    def openKdeSettings(self):
        kde_settings.open_page("kcm_powerdevilprofilesconfig")
