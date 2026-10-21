"""Desktop settings from the wizard: color scheme, pinning to the taskbar.

Each runs in the background; the user only sees the result.
"""
import configparser
import json
import logging
import os
import subprocess
from pathlib import Path

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-welcome.desktop")

# The order of the color schemes (files/system/usr/share/color-schemes); their names in the translations: "scheme.<id>"
COLOR_SCHEMES = [
    {"id": "SlothSilverDark", "colors": ["#2b2d31", "#b4b9c0", "#e3e5e8"]},
    {"id": "SlothSilverLight", "colors": ["#e3e5e8", "#68707b", "#23262a"]},
    {"id": "SlothWhite", "colors": ["#f6f7f8", "#5b6573", "#1f2328"]},
    {"id": "SlothBlack", "colors": ["#121315", "#c9cdd2", "#e6e7e9"]},
    {"id": "SlothMist", "colors": ["#dfe6ed", "#56728f", "#1f2a35"]},
    {"id": "SlothNight", "colors": ["#1f2630", "#8aa5bf", "#dde4ec"]},
    {"id": "SlothSage", "colors": ["#e1e7e0", "#56715b", "#212a23"]},
]


CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _read_ini(path):
    """A KDE settings file (group names may contain [] and % too; broken lines are skipped)."""
    ini = configparser.RawConfigParser(strict=False, interpolation=None)
    ini.optionxform = str
    try:
        ini.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as e:
        log.warning("%s: %s", path, e)
    return ini


def current_color_scheme():
    """The color scheme set right now, if it is one of ours (it should be selected when the wizard runs again)."""
    name = _read_ini(CONFIG_HOME / "kdeglobals").get("General", "ColorScheme", fallback="")
    return name if name in {c["id"] for c in COLOR_SCHEMES} else ""


def apply_color_scheme(scheme_id):
    try:
        subprocess.run(["plasma-apply-colorscheme", scheme_id], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("color scheme: %s", e)
        return False


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


def reboot():
    try:
        subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as e:
        log.warning("restart: %s", e)


def pin_to_taskbar(app_ids):
    """Pins the apps to the taskbar (through Plasma's scripting interface)."""
    if not app_ids:
        return
    launchers = [f"applications:{a}.desktop" for a in app_ids]
    script = _PIN_SCRIPT % json.dumps(launchers)
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                      GLib.Variant("(s)", (script,)), None, Gio.DBusCallFlags.NONE, 10000, None)
    except GLib.Error as e:
        log.warning("pinning to the taskbar: %s", e.message)


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


# --- Taskbar layout -------------------------------------------------------------

# Their names and descriptions in the translations: "layout.<id>.name", "layout.<id>.description"
LAYOUTS = [
    {"id": "windows10"},
    {"id": "windows11"},
    {"id": "mac"},
]

_LAYOUT_SCRIPT = """
const kind = %s;
// The pinned apps are kept
let launchers = ["applications:org.kde.dolphin.desktop", "applications:org.kde.discover.desktop",
                 "applications:org.slothos.center.desktop"];
for (const p of panels()) {
    for (const w of p.widgets()) {
        if (w.type === "org.kde.plasma.icontasks") {
            w.currentConfigGroup = ["General"];
            const l = w.readConfig("launchers", "");
            const list = Array.isArray(l) ? l : String(l).split(",").filter(x => x);
            if (list.length) launchers = list;
        }
    }
    p.remove();
}

function addTasks(panel) {
    const t = panel.addWidget("org.kde.plasma.icontasks");
    t.currentConfigGroup = ["General"];
    t.writeConfig("launchers", launchers);
    return t;
}
function addKickoff(panel) {
    const k = panel.addWidget("org.kde.plasma.kickoff");
    k.currentConfigGroup = ["General"];
    k.writeConfig("icon", "sloth-os");
}
function addTrayAndClock(panel) {
    panel.addWidget("org.kde.plasma.marginsseparator");
    panel.addWidget("org.kde.plasma.systemtray");
    panel.addWidget("org.kde.plasma.digitalclock");
}

const height = 2 * Math.floor(gridUnit * 2.5 / 2);
if (kind === "mac") {
    const top = new Panel;
    top.location = "top";
    top.height = Math.round(gridUnit * 1.6);
    addKickoff(top);
    top.addWidget("org.kde.plasma.appmenu");
    top.addWidget("org.kde.plasma.panelspacer");
    addTrayAndClock(top);
    const dock = new Panel;
    dock.location = "bottom";
    dock.height = Math.round(gridUnit * 3.2);
    dock.floating = true;
    dock.lengthMode = "fit";
    dock.alignment = "center";
    addTasks(dock);
} else {
    const panel = new Panel;
    panel.location = "bottom";
    panel.height = height;
    panel.floating = false;
    if (kind === "windows11") panel.addWidget("org.kde.plasma.panelspacer");
    addKickoff(panel);
    addTasks(panel);
    if (kind === "windows11") panel.addWidget("org.kde.plasma.panelspacer");
    addTrayAndClock(panel);
    panel.addWidget("org.kde.plasma.showdesktop");
}
"""


def current_layout():
    """The current taskbar layout from Plasma's settings: a top panel = macOS-like; with a bottom panel, if there is
    a spacer before the Start menu (centred icons) = Windows 11, otherwise Windows 10. If it cannot be told: ""."""
    ini = _read_ini(CONFIG_HOME / "plasma-org.kde.plasma.desktop-appletsrc")
    panels = {}
    for section in ini.sections():
        parts = section.split("][")
        if len(parts) == 2 and parts[0] == "Containments" and ini.get(section, "plugin", fallback="") == "org.kde.panel":
            panels[parts[1]] = ini.get(section, "location", fallback="")
    if not panels:
        return ""
    if "3" in panels.values():  # 3 = top
        return "mac"
    for cid, location in panels.items():
        if location != "4":  # 4 = bottom
            continue
        order = ini.get(f"Containments][{cid}][General", "AppletOrder", fallback="").split(";")
        plugins = [ini.get(f"Containments][{cid}][Applets][{a}", "plugin", fallback="") for a in order if a]
        if not plugins:
            plugins = [ini.get(sec, "plugin", fallback="") for sec in ini.sections()
                       if sec.startswith(f"Containments][{cid}][Applets][") and sec.count("][") == 3]
        if "org.kde.plasma.kickoff" in plugins:
            before = plugins[:plugins.index("org.kde.plasma.kickoff")]
            return "windows11" if "org.kde.plasma.panelspacer" in before else "windows10"
    return ""


def apply_layout(kind):
    if kind not in {l["id"] for l in LAYOUTS}:
        return False
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                      GLib.Variant("(s)", (_LAYOUT_SCRIPT % json.dumps(kind),)), None,
                      Gio.DBusCallFlags.NONE, 15000, None)
        return True
    except GLib.Error as e:
        log.warning("layout: %s", e.message)
        return False


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
