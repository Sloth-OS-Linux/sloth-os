"""Which apps can use the camera, the microphone and the location (Account and security page).

Read from Flatpak only, nothing is changed here: a Flatpak app reaches the microphone through the sound socket
(pulseaudio, or PipeWire directly), the camera through all devices (devices=all, which also covers game
controllers) or the camera portal, the location only through the location portal. Changing them is left to
KDE's Flatpak permissions page (the sound socket is the speaker too, all devices are the controllers too: a
switch here would break more than it fixes).
"""
import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

log = logging.getLogger("sloth-center.privacy")

KINDS = ("camera", "microphone", "location")


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return ""


def _context(text):
    """The [Context] group of `flatpak info --show-permissions`: {"sockets": {...}, "devices": {...}, ...}."""
    result, inside = {}, False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            inside = line == "[Context]"
        elif inside and "=" in line:
            key, value = line.split("=", 1)
            result[key] = {v for v in value.split(";") if v}
    return result


def _portal(text):
    """`flatpak permission-show` lines: table, id, app, permissions, data -> {(table, id): permission}."""
    result = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            result[(parts[0], parts[1])] = parts[3].strip()
    return result


def access(app_id, run=_run):
    """{"camera": bool, "microphone": bool, "location": bool} for one app."""
    context = _context(run(["flatpak", "info", "--show-permissions", app_id]))
    portal = _portal(run(["flatpak", "permission-show", app_id]))
    sockets = context.get("sockets", set())
    devices = context.get("devices", set())
    files = context.get("filesystems", set())
    pipewire = any(f.startswith("xdg-run/pipewire") and not f.startswith("!") for f in files)
    location = portal.get(("location", "location"), "")
    return {
        "camera": "all" in devices or portal.get(("devices", "camera")) == "yes",
        "microphone": "pulseaudio" in sockets or pipewire,
        "location": bool(location) and location.upper() not in ("NONE", "NO"),
    }


def overview(run=_run):
    """{"camera": [{id, name}], "microphone": [...], "location": [...]} for the installed apps, by name."""
    result = {kind: [] for kind in KINDS}
    apps = []
    for line in run(["flatpak", "list", "--app", "--columns=application,name"]).splitlines():
        parts = line.split("\t")
        if parts and parts[0]:
            apps.append((parts[0], parts[1] if len(parts) > 1 and parts[1] else parts[0]))
    for app_id, name in sorted(apps, key=lambda a: a[1].lower()):
        for kind, allowed in access(app_id, run).items():
            if allowed:
                result[kind].append({"id": app_id, "name": name})
    return result


class PrivacyController(QObject):
    changed = Signal()
    _loaded = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {kind: [] for kind in KINDS}
        self._busy = False
        self._loaded.connect(self._on_loaded)

    busy = Property(bool, lambda self: self._busy, notify=changed)
    camera = Property("QVariantList", lambda self: list(self._data["camera"]), notify=changed)
    microphone = Property("QVariantList", lambda self: list(self._data["microphone"]), notify=changed)
    location = Property("QVariantList", lambda self: list(self._data["location"]), notify=changed)

    @Slot()
    def refresh(self):
        """Looks in the background: with many apps it takes a few seconds."""
        if self._busy:
            return
        self._busy = True
        self.changed.emit()
        threading.Thread(target=lambda: self._loaded.emit(overview()), daemon=True).start()

    def _on_loaded(self, data):
        self._data = data
        self._busy = False
        self.changed.emit()

    @Slot(str)
    def openSettings(self, app_id):
        """KDE's Flatpak permissions page (for one app, if given)."""
        cmd = ["systemsettings", "kcm_flatpak"] + ([app_id] if app_id else [])
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("System Settings: %s", e)
