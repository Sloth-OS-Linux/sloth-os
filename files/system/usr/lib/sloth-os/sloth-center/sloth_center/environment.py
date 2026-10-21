"""Környezeti változók (a `~/.config/environment.d` grafikus megfelelője).

A Sloth Központ a saját fájljába ír (90-sloth-center.conf); a többi fájl változóit csak
megmutatja. A változások a következő bejelentkezéskor lépnek életbe (a systemd a
felhasználói munkamenet indulásakor olvassa be őket). Jelszó nem kell.
"""
import logging
import re
import subprocess
from pathlib import Path

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.environment")

ENV_DIR = Path.home() / ".config/environment.d"
OWN_FILE = ENV_DIR / "90-sloth-center.conf"
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
# Ha ezek rosszul vannak beállítva, a bejelentkezés vagy az appok indítása is elromolhat
RISKY = {"PATH", "HOME", "USER", "SHELL", "LD_PRELOAD", "LD_LIBRARY_PATH", "XDG_RUNTIME_DIR",
         "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "DBUS_SESSION_BUS_ADDRESS", "QT_PLUGIN_PATH",
         "QT_QPA_PLATFORM", "WAYLAND_DISPLAY", "DISPLAY"}


def _parse(path):
    """KEY=VALUE sorok (a megjegyzések és az üres sorok kimaradnak)."""
    out = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        out.append((name.strip(), value.strip()))
    return out


class EnvironmentController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._own = []
        self._other = []
        self._error = ""
        self._info = ""
        self.refresh()

    variables = Property("QVariantList", lambda self: list(self._own), notify=changed)
    otherVariables = Property("QVariantList", lambda self: list(self._other), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Slot()
    def refresh(self):
        self._own = [{"name": n, "value": v, "risky": n in RISKY} for n, v in _parse(OWN_FILE)]
        other = []
        for f in sorted(ENV_DIR.glob("*.conf")):
            if f != OWN_FILE:
                other += [{"name": n, "value": v, "file": f.name} for n, v in _parse(f)]
        self._other = other
        self.changed.emit()

    def _save(self, items):
        ENV_DIR.mkdir(parents=True, exist_ok=True)
        text = "# A Sloth Központ írja (Haladó beállítások → Környezeti változók).\n"
        text += "".join(f"{n}={v}\n" for n, v in items)
        tmp = OWN_FILE.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(OWN_FILE)

    @Slot(str, str)
    def setVariable(self, name, value):
        """Új változó, vagy egy meglévő értékének módosítása."""
        self._error, self._info = "", ""
        name, value = name.strip(), value.strip()
        if not NAME_RE.match(name):
            self._error = tr("The name can only contain English letters, numbers and underscores, and cannot start with a number (e.g. “MANGOHUD”).")
        elif "\n" in value or "\r" in value:
            self._error = tr("The value cannot span multiple lines.")
        else:
            items = [(n, v) for n, v in _parse(OWN_FILE) if n != name] + [(name, value)]
            try:
                self._save(items)
                self._info = tr("Saved. The change takes effect at the next sign-in.")
            except OSError as e:
                log.warning("mentés: %s", e)
                self._error = tr("Could not save.")
        self.refresh()

    @Slot(str)
    def removeVariable(self, name):
        self._error, self._info = "", ""
        try:
            self._save([(n, v) for n, v in _parse(OWN_FILE) if n != name])
            self._info = tr("Deleted. The change takes effect at the next sign-in.")
        except OSError as e:
            log.warning("törlés: %s", e)
            self._error = tr("Could not save.")
        self.refresh()

    @Slot()
    def openAutostart(self):
        """A KDE „Automatikus indítás” beállítása: bejelentkezéskor induló programok és szkriptek."""
        try:
            subprocess.Popen(["systemsettings", "kcm_autostart"])
        except OSError as e:
            log.warning("autostart: %s", e)

    @Slot()
    def logout(self):
        """A Plasma kijelentkezés-ablaka (a felhasználó ott még meggondolhatja)."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync("org.kde.LogoutPrompt", "/LogoutPrompt", "org.kde.LogoutPrompt", "promptLogout",
                          None, None, Gio.DBusCallFlags.NONE, 5000, None)
        except GLib.Error as e:
            log.warning("logout: %s", e.message)
