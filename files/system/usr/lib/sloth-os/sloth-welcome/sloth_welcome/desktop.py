"""Desktop settings from the wizard: color scheme, taskbar layout (pinning to the taskbar: sloth_common.taskbar).

Each runs in the background; the user only sees the result.
"""
import logging
import subprocess

from gi.repository import Gio, GLib
from sloth_common import appearance

log = logging.getLogger("sloth-welcome.desktop")

# The color schemes and taskbar layouts are shared with Sloth Center (sloth_common.appearance).
# Their names in the translations: "scheme.<id>", "layout.<id>.name", "layout.<id>.description"
COLOR_SCHEMES = appearance.COLOR_SCHEMES
LAYOUTS = [{"id": kind} for kind in appearance.LAYOUTS]
current_color_scheme = appearance.current_color_scheme
apply_color_scheme = appearance.apply_color_scheme
current_layout = appearance.current_layout
apply_layout = appearance.apply_layout


def reboot():
    try:
        subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as e:
        log.warning("restart: %s", e)


def open_network_settings():
    try:
        subprocess.Popen(["systemsettings", "kcm_networkmanagement"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.warning("network settings: %s", e)


def is_online():
    """A quick check through NetworkManager (no external request)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        res = bus.call_sync("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
                            "org.freedesktop.DBus.Properties", "Get",
                            GLib.Variant("(ss)", ("org.freedesktop.NetworkManager", "Connectivity")),
                            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 3000, None)
        # 0 = unknown (e.g. the check is turned off), 1 = none, 2 = login page,
        # 3 = limited, 4 = full
        return res.unpack()[0] in (0, 4)
    except GLib.Error:
        return True  # if we do not know, do not stand in the way of installing


# --- Quick launches at the end of the wizard ------------------------------------------------

QUICK_ACTIONS = {
    "steam": ["flatpak", "run", "com.valvesoftware.Steam"],
    "accounts": ["systemsettings", "kcm_kaccounts"],
    "language": ["systemsettings", "kcm_regionandlang"],
}


def quick_action(name):
    cmd = QUICK_ACTIONS.get(name)
    if cmd:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            log.warning("%s: %s", name, e)
