"""Asztali beállítások a varázslóból: színtéma, tálcára kitűzés.

Mindegyik a háttérben fut, a felhasználó csak az eredményt látja.
"""
import json
import logging
import subprocess

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-welcome.desktop")

# A színtémák sorrendje (files/system/usr/share/color-schemes); a nevük a fordításokban: "scheme.<id>"
COLOR_SCHEMES = [
    {"id": "SlothSilverDark", "colors": ["#2b2d31", "#b4b9c0", "#e3e5e8"]},
    {"id": "SlothSilverLight", "colors": ["#e3e5e8", "#68707b", "#23262a"]},
    {"id": "SlothWhite", "colors": ["#f6f7f8", "#5b6573", "#1f2328"]},
    {"id": "SlothBlack", "colors": ["#121315", "#c9cdd2", "#e6e7e9"]},
    {"id": "SlothMist", "colors": ["#dfe6ed", "#56728f", "#1f2a35"]},
    {"id": "SlothNight", "colors": ["#1f2630", "#8aa5bf", "#dde4ec"]},
    {"id": "SlothSage", "colors": ["#e1e7e0", "#56715b", "#212a23"]},
]


def apply_color_scheme(scheme_id):
    try:
        subprocess.run(["plasma-apply-colorscheme", scheme_id], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("színtéma: %s", e)
        return False


_PIN_SCRIPT = """
const add = %s;
for (const panel of panels()) {
    for (const w of panel.widgets()) {
        if (w.type !== "org.kde.plasma.icontasks" && w.type !== "org.kde.plasma.taskmanager") continue;
        w.currentConfigGroup = ["General"];
        let cur = w.readConfig("launchers", "");
        let list = Array.isArray(cur) ? cur.slice() : (cur ? String(cur).split(",") : []);
        // a fájlkezelő után kerüljenek, mint a Windowsban
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
    """Frissen telepített appok: a Plasma lássa a Start menü bejegyzésüket és az ikonjukat.

    Enélkül a tálcán az általános ikon látszott újraindításig: a bejegyzések gyorsítótárát
    (kbuildsycoca6) újraépítjük, és szólunk a futó programoknak, hogy töltsék újra az ikonokat.
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
        log.warning("ikonok újratöltése: %s", e.message)


def reboot():
    try:
        subprocess.Popen(["systemctl", "reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError as e:
        log.warning("újraindítás: %s", e)


def pin_to_taskbar(app_ids):
    """Kitűzi az appokat a tálcára (a Plasma szkriptfelületén keresztül)."""
    if not app_ids:
        return
    launchers = [f"applications:{a}.desktop" for a in app_ids]
    script = _PIN_SCRIPT % json.dumps(launchers)
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell", "evaluateScript",
                      GLib.Variant("(s)", (script,)), None, Gio.DBusCallFlags.NONE, 10000, None)
    except GLib.Error as e:
        log.warning("tálcára kitűzés: %s", e.message)


def open_network_settings():
    try:
        subprocess.Popen(["systemsettings", "kcm_networkmanagement"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.warning("hálózati beállítások: %s", e)


def is_online():
    """Gyors ellenőrzés a NetworkManageren keresztül (nincs külső kérés)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        res = bus.call_sync("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager",
                            "org.freedesktop.DBus.Properties", "Get",
                            GLib.Variant("(ss)", ("org.freedesktop.NetworkManager", "Connectivity")),
                            GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 3000, None)
        # 0 = ismeretlen (pl. ki van kapcsolva az ellenőrzés), 1 = nincs, 2 = bejelentkező oldal,
        # 3 = korlátozott, 4 = teljes
        return res.unpack()[0] in (0, 4)
    except GLib.Error:
        return True  # ha nem tudjuk, ne akadályozzuk a telepítést


# --- Tálca-elrendezés -------------------------------------------------------------

# A nevük és leírásuk a fordításokban: "layout.<id>.name", "layout.<id>.description"
LAYOUTS = [
    {"id": "windows10"},
    {"id": "windows11"},
    {"id": "mac"},
]

_LAYOUT_SCRIPT = """
const kind = %s;
// A rögzített appokat megtartjuk
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
        log.warning("elrendezés: %s", e.message)
        return False


# --- Gyors indítások a varázsló végén ------------------------------------------------

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
