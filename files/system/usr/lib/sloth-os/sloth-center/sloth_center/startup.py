"""Programs that start by themselves at sign-in (Services page).

Only the user's own entries (~/.config/autostart: Steam, Discord, … when they were set to start at sign-in, also
through the Flatpak background portal). The system's parts (/etc/xdg/autostart: the password store, the tray
helpers, …) are not listed: turning those off would break something. Turning a program off is the same as in
KDE's own settings: Hidden=true in its entry; turning it on again removes that.
"""
import configparser
import logging
import os
import re
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import catalog, tr

log = logging.getLogger("sloth-center.startup")

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
AUTOSTART = CONFIG_HOME / "autostart"
SYSTEM_DIRS = [Path(d) / "autostart" for d in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":") if d]
GROUP = "Desktop Entry"


def _read(path):
    ini = configparser.RawConfigParser(strict=False, interpolation=None)
    ini.optionxform = str
    try:
        ini.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as e:
        log.warning("%s: %s", path, e)
    return ini


def _localized(ini, key):
    """Name[hu], Name[pt_BR] … in the language of Sloth Center, otherwise the plain value."""
    lang = catalog.language() or ""
    for k in (f"{key}[{lang}]", f"{key}[{lang.split('_')[0]}]", key):
        value = ini.get(GROUP, k, fallback="")
        if value:
            return value
    return ""


def _is_enabled(ini):
    return (ini.get(GROUP, "Hidden", fallback="false").lower() != "true"
            and ini.get(GROUP, "X-GNOME-Autostart-enabled", fallback="true").lower() != "false")


def entries():
    """The user's own autostart programs: [{file, name, description, icon, enabled}]."""
    result = []
    for path in sorted(AUTOSTART.glob("*.desktop")):
        # a file with the name of a system entry only switches that system part on or off: not ours to show
        if any((d / path.name).exists() for d in SYSTEM_DIRS):
            continue
        ini = _read(path)
        if not ini.has_section(GROUP) or ini.get(GROUP, "Type", fallback="Application") != "Application":
            continue
        name = _localized(ini, "Name") or path.stem
        result.append({
            "file": path.name,
            "name": name,
            "description": _localized(ini, "Comment"),
            "icon": ini.get(GROUP, "Icon", fallback="") or "application-x-executable",
            "enabled": _is_enabled(ini),
        })
    return sorted(result, key=lambda e: e["name"].lower())


def _set_key(text, key, value):
    """Sets (or with value None removes) a key in the [Desktop Entry] group, leaving the rest of the file as it is."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == f"[{GROUP}]"), None)
    if start is None:
        lines = [f"[{GROUP}]"] + lines
        start = 0
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    lines = lines[:start + 1] + [l for l in lines[start + 1:end] if not pattern.match(l)] + lines[end:]
    if value is not None:
        lines.insert(start + 1, f"{key}={value}")
    return "\n".join(lines) + "\n"


def set_enabled(file_name, enabled):
    path = AUTOSTART / Path(file_name).name
    text = path.read_text(encoding="utf-8")
    if enabled:
        text = _set_key(text, "Hidden", None)
        if "X-GNOME-Autostart-enabled" in text:
            text = _set_key(text, "X-GNOME-Autostart-enabled", "true")
    else:
        text = _set_key(text, "Hidden", "true")
    path.write_text(text, encoding="utf-8")


class StartupController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        self._error = ""
        self.refresh()

    programs = Property("QVariantList", lambda self: list(self._entries), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)

    @Slot()
    def refresh(self):
        self._entries = entries()
        self.changed.emit()

    @Slot(str, bool)
    def setEnabled(self, file_name, enabled):
        try:
            set_enabled(file_name, enabled)
            self._error = ""
        except OSError as e:
            log.warning("%s: %s", file_name, e)
            self._error = tr("Couldn't change the startup setting. Please try again.")
        self.refresh()
