"""The taskbar: pinning apps the user chose (Sloth Welcome, the .exe handler).

Only what the user installed and asked for goes on the taskbar. The pins are written through Plasma's scripting
interface, next to the file manager, as on Windows.
"""
import json
import logging
import subprocess

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-os.taskbar")

_PIN_SCRIPT = """
const add = %s;
for (const panel of panels()) {
    for (const w of panel.widgets()) {
        if (w.type !== "org.kde.plasma.icontasks" && w.type !== "org.kde.plasma.taskmanager") continue;
        w.currentConfigGroup = ["General"];
        let cur = w.readConfig("launchers", "");
        let list = Array.isArray(cur) ? cur.slice() : (cur ? String(cur).split(",") : []);
        // they should come after the file manager, as in Windows
        let pos = Math.min(1, list.length);
        for (const item of add) {
            if (list.indexOf(item) === -1) { list.splice(pos, 0, item); pos++; }
        }
        w.writeConfig("launchers", list);
        w.reloadConfig();
    }
}
"""


def refresh_app_cache():
    """Freshly installed apps: Plasma should see their Start menu entries and icons.

    Without this the taskbar showed the generic icon until a restart: the entries' cache
    (kbuildsycoca6) is rebuilt, and the running programs are told to reload their icons.
    """
    try:
        subprocess.run(["kbuildsycoca6"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("kbuildsycoca6: %s", e)
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.emit_signal(None, "/KIconLoader", "org.kde.KIconLoader", "iconChanged", GLib.Variant("(i)", (0,)))
        bus.flush_sync(None)
    except GLib.Error as e:
        log.warning("reloading icons: %s", e.message)


def pin(desktop_ids):
    """Pins the apps to the taskbar. desktop_ids: the Start menu entries' names without ".desktop"
    (a Flatpak's app ID, or e.g. "sloth-win-battlenet-battle-net-launcher")."""
    if not desktop_ids:
        return
    launchers = [f"applications:{a}.desktop" for a in desktop_ids]
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                      GLib.Variant("(s)", (_PIN_SCRIPT % json.dumps(launchers),)), None, Gio.DBusCallFlags.NONE,
                      10000, None)
    except GLib.Error as e:
        log.warning("pinning to the taskbar: %s", e.message)
