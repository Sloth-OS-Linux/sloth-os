"""The look of the desktop: color schemes and taskbar layouts (Windows 10, Windows 11, macOS-like, Ubuntu-like).

Sloth Welcome offers them at the first start, Sloth Center (Appearance) any time later; both use these same
functions, so a layout looks the same whichever set it. The pinned apps are kept. The small drawing of each layout:
qml/SlothCommon/LayoutPreview.qml.
"""
import configparser
import json
import logging
import os
import re
import subprocess
from pathlib import Path

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-os.appearance")

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
# The folder to add to the QML engine's import paths for "import SlothCommon"
QML_IMPORT_PATH = str(Path(__file__).resolve().parent / "qml")

# The order of the color schemes (files/system/usr/share/color-schemes); their names are in each tool's translations
COLOR_SCHEMES = [
    {"id": "SlothSilverDark", "colors": ["#2b2d31", "#b4b9c0", "#e3e5e8"]},
    {"id": "SlothSilverLight", "colors": ["#e3e5e8", "#68707b", "#23262a"]},
    {"id": "SlothWhite", "colors": ["#f6f7f8", "#5b6573", "#1f2328"]},
    {"id": "SlothBlack", "colors": ["#121315", "#c9cdd2", "#e6e7e9"]},
    {"id": "SlothMist", "colors": ["#dfe6ed", "#56728f", "#1f2a35"]},
    {"id": "SlothNight", "colors": ["#1f2630", "#8aa5bf", "#dde4ec"]},
    {"id": "SlothSage", "colors": ["#e1e7e0", "#56715b", "#212a23"]},
]

# "Your own color": an accent color on top of any scheme (the highlights, selected items, buttons and sliders).
# plasma-apply-colorscheme --accent-color tints the current scheme but does not remember it, and the next scheme
# drops it (tried 2026-10-30). So the choice is kept where KDE's own color settings keep it (kdeglobals [General]
# AccentColor, "r,g,b") and set again after every scheme change. "" = the scheme's own color.
ACCENT_COLORS = ["#3d8fd9", "#1aa39a", "#3fa34d", "#e0a526", "#e0662b", "#d6404a", "#d6457e", "#8a5cd6"]
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Their names and descriptions are in each tool's translations
LAYOUTS =["windows10", "windows11", "mac", "ubuntu"]

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
} else if (kind === "ubuntu") {
    // A top bar with the date and time in the middle, a dock on the left with the app grid at its end
    const top = new Panel;
    top.location = "top";
    top.height = Math.round(gridUnit * 1.6);
    top.addWidget("org.kde.plasma.panelspacer");
    const clock = top.addWidget("org.kde.plasma.digitalclock");
    clock.currentConfigGroup = ["Appearance"];
    clock.writeConfig("showDate", true);
    clock.writeConfig("dateDisplayFormat", "BesideTime");
    top.addWidget("org.kde.plasma.panelspacer");
    top.addWidget("org.kde.plasma.systemtray");
    // Floating and only as tall as its icons: it does not run into the top bar, its corners are rounded
    const dock = new Panel;
    dock.location = "left";
    dock.height = Math.round(gridUnit * 3.2);
    dock.floating = true;
    dock.lengthMode = "fit";
    dock.alignment = "center";
    addTasks(dock);
    dock.addWidget("org.kde.plasma.marginsseparator");
    // The app grid: the Start menu with large icons in a grid, sliding out from the dock
    const grid = dock.addWidget("org.kde.plasma.kickoff");
    grid.currentConfigGroup = ["General"];
    grid.writeConfig("icon", "view-app-grid-symbolic");
    grid.writeConfig("favoritesDisplay", 0);     // 0 = grid
    grid.writeConfig("applicationsDisplay", 0);
    // a roomy popup (Plasma keeps its size at the top of the widget's settings, not in General)
    grid.currentConfigGroup = [];
    grid.writeConfig("popupWidth", Math.round(gridUnit * 50));
    grid.writeConfig("popupHeight", Math.round(gridUnit * 36));
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


def read_ini(path):
    """A KDE settings file (group names may contain [] and % too; broken lines are skipped)."""
    ini = configparser.RawConfigParser(strict=False, interpolation=None)
    ini.optionxform = str
    try:
        ini.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as e:
        log.warning("%s: %s", path, e)
    return ini


def current_color_scheme():
    """The color scheme set right now, if it is one of ours."""
    name = read_ini(CONFIG_HOME / "kdeglobals").get("General", "ColorScheme", fallback="")
    return name if name in {c["id"] for c in COLOR_SCHEMES} else ""


def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)


def apply_color_scheme(scheme_id):
    if scheme_id not in {c["id"] for c in COLOR_SCHEMES}:
        return False
    try:
        _run(["plasma-apply-colorscheme", scheme_id])
        accent = current_accent()
        if accent:
            _run(["plasma-apply-colorscheme", "--accent-color", accent])
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("color scheme: %s", e)
        return False


def current_accent():
    """The own accent color ("#rrggbb"), or "" for the scheme's own."""
    value = read_ini(CONFIG_HOME / "kdeglobals").get("General", "AccentColor", fallback="")
    try:
        r, g, b = (int(x) for x in value.split(",")[:3])
        return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        return value if _HEX.match(value) else ""


def apply_accent(color):
    """Sets the own accent color ("#rrggbb"), or goes back to the scheme's own ("")."""
    if color and not _HEX.match(color):
        return False
    try:
        if color:
            rgb = ",".join(str(int(color[i:i + 2], 16)) for i in (1, 3, 5))
            _run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "AccentColor", rgb])
            _run(["plasma-apply-colorscheme", "--accent-color", color])
            return True
        _run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "AccentColor", "--delete"])
        # The scheme's own colors again: plasma-apply-colorscheme refuses the scheme already set, so it is
        # forgotten first (nothing is applied in between, so the screen does not flash)
        scheme = read_ini(CONFIG_HOME / "kdeglobals").get("General", "ColorScheme", fallback="")
        if scheme:
            _run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "ColorScheme", "--delete"])
            _run(["plasma-apply-colorscheme", scheme])
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("accent color: %s", e)
        return False


def current_titlebar_accent():
    """Whether the windows' title bars take the highlight color too (KDE's own setting, as in System Settings)."""
    return read_ini(CONFIG_HOME / "kdeglobals").get("General", "TitlebarIsAccentColored",
                                                    fallback="false").lower() == "true"


def apply_titlebar_accent(on):
    """The title bars in the highlight color too, or in the scheme's own; plasma-apply-colorscheme reads the setting
    when it applies the colors, so they are applied again."""
    try:
        if on:
            _run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "TitlebarIsAccentColored",
                  "--type", "bool", "true"])
        else:
            _run(["kwriteconfig6", "--file", "kdeglobals", "--group", "General", "--key", "TitlebarIsAccentColored",
                  "--delete"])
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("title bar color: %s", e)
        return False
    return apply_accent(current_accent())


def current_layout():
    """The current taskbar layout from Plasma's settings: a top panel with a left one = Ubuntu-like, with another =
    macOS-like; with a bottom panel only, if there is a spacer before the Start menu (centred icons) = Windows 11,
    otherwise Windows 10. If it cannot be told: ""."""
    ini = read_ini(CONFIG_HOME / "plasma-org.kde.plasma.desktop-appletsrc")
    panels = {}
    for section in ini.sections():
        parts = section.split("][")
        if len(parts) == 2 and parts[0] == "Containments" and ini.get(section, "plugin", fallback="") == "org.kde.panel":
            panels[parts[1]] = ini.get(section, "location", fallback="")
    if not panels:
        return ""
    if "3" in panels.values():  # 3 = top
        return "ubuntu" if "5" in panels.values() else "mac"  # 5 = left
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
    if kind not in LAYOUTS:
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
