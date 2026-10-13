"""Asztali beállítások a varázslóból: színtéma, tálcára kitűzés.

Mindegyik a háttérben fut, a felhasználó csak az eredményt látja.
"""
import json
import logging
import subprocess

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-welcome.desktop")

# A színtémák sorrendje és megjelenített neve (files/system/usr/share/color-schemes)
COLOR_SCHEMES = [
    {"id": "SlothSilverDark", "name": "Ezüst (sötét)", "colors": ["#2b2d31", "#b4b9c0", "#e3e5e8"]},
    {"id": "SlothSilverLight", "name": "Ezüst (világos)", "colors": ["#e3e5e8", "#68707b", "#23262a"]},
    {"id": "SlothWhite", "name": "Hófehér", "colors": ["#f6f7f8", "#5b6573", "#1f2328"]},
    {"id": "SlothBlack", "name": "Éjfekete", "colors": ["#121315", "#c9cdd2", "#e6e7e9"]},
    {"id": "SlothMist", "name": "Ködkék", "colors": ["#dfe6ed", "#56728f", "#1f2a35"]},
    {"id": "SlothNight", "name": "Éjkék", "colors": ["#1f2630", "#8aa5bf", "#dde4ec"]},
    {"id": "SlothSage", "name": "Zsálya", "colors": ["#e1e7e0", "#56715b", "#212a23"]},
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
