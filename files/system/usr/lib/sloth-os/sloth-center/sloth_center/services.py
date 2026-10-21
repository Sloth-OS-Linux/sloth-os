"""Szolgáltatások be- és kikapcsolása (a `systemctl` grafikus megfelelője).

A systemd D-Bus API-ját használja; a jogosultságot igénylő műveleteknél a
polkit grafikus jelszókérő ablakot mutat. A gyakori szolgáltatások érthető
névvel jelennek meg, a többi a haladó listában.

A felhasználó saját szolgáltatásai (`systemctl --user`) a munkamenet buszán
érhetők el; ezekhez nem kell jelszó.
"""
import logging

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import N_, tr

log = logging.getLogger("sloth-center.services")

SD = "org.freedesktop.systemd1"
SD_PATH = "/org/freedesktop/systemd1"
SD_MANAGER = SD + ".Manager"
INTERACTIVE = Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION

# (unit, név, leírás). Több unit esetén az első létező számít.
COMMON = [
    (["bluetooth.service"], "Bluetooth", N_("Wireless headphones, controllers, mice.")),
    (["cups.service"], N_("Printing"), N_("Use printers.")),
    (["firewalld.service"], N_("Firewall"), N_("Protects the computer from unwanted connections from the network.")),
    (["uupd.timer", "rpm-ostreed-automatic.timer"], N_("Automatic updates"),
     N_("System and app updates download in the background.")),
    (["avahi-daemon.service"], N_("Find devices on the network"),
     N_("Automatically find network printers, shares and other devices.")),
    (["sshd.service"], N_("Remote login (SSH)"),
     N_("Lets someone log in to this computer from another one using a command line. If you don't know what this is, leave it off.")),
    (["smb.service"], N_("File sharing with Windows computers"), N_("Shared folders can be reached from other computers.")),
]


# A munkamenet alapjai: ezek leállítása az egész asztalt (hang, ablakok, bejelentkezés) elrontaná,
# ezért a saját szolgáltatások listájában csak látszanak, nem állíthatók
PROTECTED_USER_PREFIXES = (
    "dbus", "pipewire", "wireplumber", "plasma-", "kwin", "kded", "ksmserver", "xdg-", "at-spi",
    "systemd-", "graphical-session", "gvfs", "gcr-", "p11-kit", "flatpak-", "app-", "obex", "kactivitymanagerd",
    "sloth-")


def _human_error(raw):
    low = (raw or "").lower()
    if any(k in low for k in ("not authorized", "access denied", "authentication", "interactive")):
        return tr("This needs administrator approval. Try again and enter your password.")
    if "masked" in low:
        return tr("The system has blocked this service, so it can't be turned on.")
    return tr("Couldn't change it. Try again later.")


class ServicesController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bus = None
        self._user_bus = None
        self._common = []
        self._all = []
        self._user = []
        self._error = ""
        self._busy_unit = ""
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error as e:
            log.error("system bus: %s", e.message)
        try:
            self._user_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            log.error("session bus: %s", e.message)
        self.refresh()

    # --- Tulajdonságok ---------------------------------------------------------

    common = Property("QVariantList", lambda self: list(self._common), notify=changed)
    allServices = Property("QVariantList", lambda self: list(self._all), notify=changed)
    userServices = Property("QVariantList", lambda self: list(self._user), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    busyUnit = Property(str, lambda self: self._busy_unit, notify=changed)

    # --- Lekérdezés ----------------------------------------------------------------

    def _call(self, method, params=None, reply=None, flags=Gio.DBusCallFlags.NONE, bus=None):
        return (bus or self._bus).call_sync(SD, SD_PATH, SD_MANAGER, method, params,
                                            GLib.VariantType(reply) if reply else None, flags, 30000, None)

    def _unit_file_state(self, unit):
        try:
            return self._call("GetUnitFileState", GLib.Variant("(s)", (unit,)), "(s)").unpack()[0]
        except GLib.Error:
            return None  # nincs ilyen unit a gépen

    def _active_state(self, unit):
        try:
            path = self._call("LoadUnit", GLib.Variant("(s)", (unit,)), "(o)").unpack()[0]
            v = self._bus.call_sync(SD, path, "org.freedesktop.DBus.Properties", "Get",
                                    GLib.Variant("(ss)", (SD + ".Unit", "ActiveState")),
                                    GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 5000, None)
            return v.unpack()[0]
        except GLib.Error:
            return "inactive"

    @Slot()
    def refresh(self):
        if not self._bus:
            return
        common = []
        for units, name, desc in COMMON:
            for unit in units:
                state = self._unit_file_state(unit)
                if state is None:
                    continue
                active = self._active_state(unit)
                common.append({"unit": unit, "name": tr(name), "description": tr(desc),
                               "enabled": state in ("enabled", "enabled-runtime", "alias")
                               or active == "active",
                               "locked": state in ("masked", "static", "indirect", "generated")})
                break
        self._common = common
        try:
            units = self._call("ListUnits", None, "(a(ssssssouso))").unpack()[0]
        except GLib.Error as e:
            log.warning("ListUnits: %s", e.message)
            units = []
        self._all = sorted(
            [{"unit": u[0], "description": u[1], "active": u[3] == "active", "sub": u[4]}
             for u in units if u[0].endswith(".service") and u[2] == "loaded"],
            key=lambda x: x["description"].lower())
        self._user = self._user_services()
        self.changed.emit()

    def _user_services(self):
        """A felhasználó szolgáltatásai: amelyek most be vannak töltve, és amelyeket be lehet kapcsolni."""
        if not self._user_bus:
            return []
        try:
            loaded = self._call("ListUnits", None, "(a(ssssssouso))", bus=self._user_bus).unpack()[0]
            files = self._call("ListUnitFiles", None, "(a(ss))", bus=self._user_bus).unpack()[0]
        except GLib.Error as e:
            log.warning("user units: %s", e.message)
            return []
        states = {f.rsplit("/", 1)[-1]: state for f, state in files}
        out = {}
        for u in loaded:
            if u[0].endswith(".service") and u[2] == "loaded" and "@" not in u[0]:
                out[u[0]] = {"unit": u[0], "description": u[1], "active": u[3] == "active"}
        # bekapcsolható, de most nem futó szolgáltatások (pl. kikapcsolt háttérprogramok)
        for unit, state in states.items():
            if unit.endswith(".service") and "@" not in unit and unit not in out and state in ("enabled", "disabled"):
                out[unit] = {"unit": unit, "description": unit.removesuffix(".service"), "active": False}
        for item in out.values():
            state = states.get(item["unit"], "static")
            item["protected"] = item["unit"].startswith(PROTECTED_USER_PREFIXES)
            item["enabled"] = state in ("enabled", "enabled-runtime", "linked")
            item["switchable"] = state in ("enabled", "disabled") and not item["protected"]
        return sorted(out.values(), key=lambda x: x["description"].lower())

    # --- Műveletek -----------------------------------------------------------------

    def _async(self, method, params, then, bus=None):
        def done(bus, res):
            try:
                bus.call_finish(res)
            except GLib.Error as e:
                log.warning("%s: %s", method, e.message)
                self._error = _human_error(e.message)
                self._busy_unit = ""
                self.refresh()
                return
            then()
        (bus or self._bus).call(SD, SD_PATH, SD_MANAGER, method, params, None, INTERACTIVE, 60000, None, done)

    @Slot(str, bool)
    def setEnabled(self, unit, enabled):
        """Bekapcsolás = indításkor induljon + induljon el most; kikapcsolás fordítva."""
        self._error = ""
        self._busy_unit = unit
        self.changed.emit()

        def finish():
            self._busy_unit = ""
            self.refresh()

        def reload_then(next_step):
            return lambda: self._async("Reload", None, next_step)

        if enabled:
            self._async("EnableUnitFiles", GLib.Variant("(asbb)", ([unit], False, True)),
                        reload_then(lambda: self._async("StartUnit", GLib.Variant("(ss)", (unit, "replace")), finish)))
        else:
            self._async("StopUnit", GLib.Variant("(ss)", (unit, "replace")),
                        lambda: self._async("DisableUnitFiles", GLib.Variant("(asb)", ([unit], False)),
                                            reload_then(finish)))

    @Slot(str, bool)
    def setRunning(self, unit, running):
        """Haladó lista: csak indítás / leállítás most (a bekapcsolt állapot nem változik)."""
        self._error = ""
        self._busy_unit = unit
        self.changed.emit()

        def finish():
            self._busy_unit = ""
            self.refresh()

        self._async("StartUnit" if running else "StopUnit", GLib.Variant("(ss)", (unit, "replace")), finish)

    # --- A felhasználó saját szolgáltatásai (jelszó nélkül) ----------------------------

    @Slot(str, bool)
    def setUserEnabled(self, unit, enabled):
        """Bejelentkezéskor induljon-e (és most is indul / leáll)."""
        self._error = ""
        self._busy_unit = unit
        self.changed.emit()
        bus = self._user_bus

        def finish():
            self._busy_unit = ""
            self.refresh()

        def reload_then(next_step):
            return lambda: self._async("Reload", None, next_step, bus=bus)

        if enabled:
            self._async("EnableUnitFiles", GLib.Variant("(asbb)", ([unit], False, True)),
                        reload_then(lambda: self._async("StartUnit", GLib.Variant("(ss)", (unit, "replace")),
                                                        finish, bus=bus)), bus=bus)
        else:
            self._async("StopUnit", GLib.Variant("(ss)", (unit, "replace")),
                        lambda: self._async("DisableUnitFiles", GLib.Variant("(asb)", ([unit], False)),
                                            reload_then(finish), bus=bus), bus=bus)

    @Slot(str, bool)
    def setUserRunning(self, unit, running):
        self._error = ""
        self._busy_unit = unit
        self.changed.emit()

        def finish():
            self._busy_unit = ""
            self.refresh()

        self._async("StartUnit" if running else "StopUnit", GLib.Variant("(ss)", (unit, "replace")), finish,
                    bus=self._user_bus)
