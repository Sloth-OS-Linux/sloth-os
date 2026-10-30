"""Sloth OS's own settings in one file, to take them along to a reinstalled or another computer (File backup page).

What goes in: the settings files Sloth OS writes (~/.config/sloth-os: sharing, the disc image choice, the display and
sound profiles, where Windows programs go, the developer panel, the quiet hours), the look (color scheme and taskbar
layout, the same ones as in the welcome wizard) and the installed apps (their Flatpak ids). Nothing personal: no
files, no passwords, no accounts. Restoring writes the files back and sets the look again; a program location on a
drive this computer does not have is left out. The apps are offered in Sloth Welcome, ticked (welcome_selection):
the wizard keeps only the ones its catalog knows and does not install again what is already there.
"""
import datetime
import json
import os
import re
import subprocess
from pathlib import Path

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os"
FORMAT = "sloth-os-settings"
VERSION = 1
# The settings files that are worth taking along (only these are read and written)
FILES = ("community.json", "disc-images.json", "profiles.json", "applications.json", "devpanel.json",
         "quiet-hours.json")
MAX_BYTES = 1024 * 1024
# Sloth Welcome continues from this file (its own name for it: PROGRESS)
WELCOME_PROGRESS = CONFIG / "welcome-progress.json"
APP_ID = re.compile(r"[A-Za-z0-9_.-]{3,255}")


def installed_apps():
    """The installed Flatpak apps (user and system), by id."""
    try:
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return sorted({line.strip() for line in out.splitlines() if APP_ID.fullmatch(line.strip())})


def collect(config=None, appearance=None, apps=None):
    """The backup as a dictionary. appearance: {"scheme", "layout"} (the caller reads them from KDE); apps: ids."""
    config = Path(config or CONFIG)
    files = {}
    for name in FILES:
        path = config / name
        try:
            if path.stat().st_size <= MAX_BYTES:
                files[name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {"format": FORMAT, "version": VERSION,
            "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "files": files, "appearance": {k: v for k, v in (appearance or {}).items() if v},
            "apps": [a for a in (apps or []) if isinstance(a, str) and APP_ID.fullmatch(a)]}


def backup_apps(backup):
    return [a for a in backup.get("apps", []) if isinstance(a, str) and APP_ID.fullmatch(a)]


def welcome_selection(apps, progress=None):
    """Ticks the apps in Sloth Welcome: it opens at the first app step with them selected (added to a selection
    already there). The passwords and sharing steps are skipped as already done; nothing else is changed."""
    progress = Path(progress or WELCOME_PROGRESS)
    try:
        state = json.loads(progress.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    selected = [a for a in state.get("selected", []) if isinstance(a, str)]
    state["selected"] = selected + [a for a in apps if a not in selected]
    if state.get("step") in (None, "", "welcome", "look", "security", "sharing", "windows"):
        state["step"] = "cat0"
    progress.parent.mkdir(parents=True, exist_ok=True)
    progress.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return state


def write(path, backup):
    Path(path).write_text(json.dumps(backup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path):
    """The backup from a file, or None if it is not one (another JSON file, too big, broken)."""
    try:
        path = Path(path)
        if path.stat().st_size > 8 * MAX_BYTES:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("files"), dict):
        return None
    return data


def _merge_libraries(saved, current):
    """Where Windows programs go: the saved places that exist on this computer, plus the current ones."""
    saved = saved if isinstance(saved, dict) else {}
    current = current if isinstance(current, dict) else {}
    out = dict(current)
    places = [p for p in saved.get("libraries", []) if isinstance(p, str) and Path(p).is_dir()]
    out["libraries"] = list(dict.fromkeys(places + list(current.get("libraries", []))))
    if isinstance(saved.get("default"), str) and saved["default"] in places:
        out["default"] = saved["default"]
    return out


def restore(backup, config=None):
    """Writes the settings files back. -> the names written."""
    config = Path(config or CONFIG)
    config.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in backup.get("files", {}).items():
        if name not in FILES:
            continue   # only our own files, whatever the backup says
        if name == "applications.json":
            try:
                current = json.loads((config / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                current = {}
            content = _merge_libraries(content, current)
        (config / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(name)
    return written


# --- Sloth Center ----------------------------------------------------------------------------------------------

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot  # noqa: E402

from sloth_common import appearance  # noqa: E402

from .i18n import tr  # noqa: E402


def _local(url):
    return QUrl(url).toLocalFile() if url.startswith("file:") else url


class SettingsBackupController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._ok = True
        self._apps = []   # the apps of the loaded file, to offer in Sloth Welcome

    resultText = Property(str, lambda self: self._text, notify=changed)
    resultOk = Property(bool, lambda self: self._ok, notify=changed)
    appsCount = Property(int, lambda self: len(self._apps), notify=changed)

    @Property(str, constant=True)
    def suggestedName(self):
        return f"Sloth OS settings {datetime.date.today().isoformat()}.json"

    def _done(self, ok, text):
        self._ok, self._text = ok, text
        self.changed.emit()

    @Slot(str)
    def exportTo(self, url):
        path = _local(url)
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        look = {"scheme": appearance.current_color_scheme(), "accent": appearance.current_accent(),
                "layout": appearance.current_layout()}
        try:
            write(path, collect(appearance=look, apps=installed_apps()))
        except OSError:
            self._done(False, tr("Couldn't save the settings there. Choose another folder."))
            return
        self._done(True, tr("Settings saved: {file}", file=Path(path).name))

    @Slot(str)
    def importFrom(self, url):
        backup = read(_local(url))
        if backup is None:
            self._done(False, tr("This file doesn't contain Sloth OS settings."))
            return
        try:
            restore(backup)
        except OSError:
            self._done(False, tr("Couldn't load the settings. Please try again."))
            return
        look = backup.get("appearance", {})
        if look.get("scheme"):
            appearance.apply_color_scheme(look["scheme"])
        if "accent" in look:  # files saved before 2026-10-30 have none: the color stays as it is
            appearance.apply_accent(look["accent"])
        if look.get("layout"):
            appearance.apply_layout(look["layout"])
        self._apps = backup_apps(backup)
        self._done(True, tr("Settings loaded. Open Sloth Center again to see them everywhere."))

    @Slot()
    def installApps(self):
        """Sloth Welcome with the saved apps ticked (it installs the ones its catalog knows)."""
        if not self._apps:
            return
        try:
            welcome_selection(self._apps)
            subprocess.Popen(["sloth-welcome"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            self._done(False, tr("Couldn't open Sloth Welcome."))
            return
        self._apps = []
        self.changed.emit()
