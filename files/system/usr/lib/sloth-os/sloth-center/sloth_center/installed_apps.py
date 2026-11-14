"""Apps (Sloth Center → Apps; AppsPage.qml): every app installed on the computer (Flatpaks, for everyone and only for
this account), with Open and Remove, like the Apps page of Windows' Settings. Windows programs have a page of their
own (Windows programs, winprograms.py); runtimes and other parts that apps need are not listed.

Read and removed with libflatpak (as Sloth Welcome installs). Removing an app installed for everyone asks for an
administrator's password where polkit wants one (a child account cannot remove apps on its own). "Also delete its
settings and saved data" removes ~/.var/app/<app ID>, as `flatpak uninstall --delete-data` does.
"""
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

log = logging.getLogger("sloth-center.apps")

APP_ID = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)+$")


def _flatpak():
    import gi
    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak
    return Flatpak


def _desktop_name(app_id):
    """The app's name in the user's language, from its start menu entry ("" if it has none)."""
    try:
        from gi.repository import Gio
        info = Gio.DesktopAppInfo.new(app_id + ".desktop")
        return info.get_name() if info else ""
    except (ImportError, TypeError):
        return ""


def installations():
    """[(installation, "system" | "user")] that exist."""
    Flatpak = _flatpak()
    out = []
    for kind, make in (("system", lambda: Flatpak.Installation.new_system(None)),
                       ("user", lambda: Flatpak.Installation.new_user(None))):
        try:
            out.append((make(), kind))
        except Exception as e:  # noqa: BLE001 - e.g. no user installation yet
            log.info("flatpak %s installation: %s", kind, e)
    return out


def list_apps():
    """[{id, name, summary, version, size, scope}] by name; the same app in both places shows twice (with its scope)."""
    Flatpak = _flatpak()
    apps = []
    for inst, scope in installations():
        try:
            refs = inst.list_installed_refs_by_kind(Flatpak.RefKind.APP, None)
        except Exception as e:  # noqa: BLE001
            log.warning("listing the %s apps: %s", scope, e)
            continue
        for ref in refs:
            app_id = ref.get_name()
            apps.append({
                "id": app_id,
                "name": _desktop_name(app_id) or ref.get_appdata_name() or app_id,
                "summary": ref.get_appdata_summary() or "",
                "version": ref.get_appdata_version() or "",
                "size": int(ref.get_installed_size() or 0),
                "scope": scope,
                "ref": ref.format_ref(),
            })
    return sorted(apps, key=lambda a: (a["name"].casefold(), a["scope"]))


def data_dir(app_id, home=None):
    """~/.var/app/<id>, only for a real app ID (never a path that leads elsewhere)."""
    if not APP_ID.match(app_id or ""):
        return None
    return Path(home or Path.home()) / ".var" / "app" / app_id


def remove(ref, scope, delete_data):
    """(ok, error text). Runs a libflatpak transaction (polkit asks for a password where needed)."""
    Flatpak = _flatpak()
    inst = next((i for i, s in installations() if s == scope), None)
    if inst is None:
        return False, "no installation"
    try:
        txn = Flatpak.Transaction.new_for_installation(inst, None)
        txn.add_uninstall(ref)
        txn.run(None)
    except Exception as e:  # noqa: BLE001 - cancelled at the password, or flatpak said no
        log.warning("removing %s: %s", ref, e)
        return False, str(e)
    if delete_data:
        path = data_dir(ref.split("/")[1] if "/" in ref else "")
        if path and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    return True, ""


class AppsController(QObject):
    """QML (context property "installedApps"): apps, loaded, busy (the ref being removed), error; refresh(),
    open(id), remove(ref, scope, deleteData), getMore()."""
    changed = Signal()
    _listed = Signal(list)
    _removed = Signal(str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps, self._loaded, self._busy, self._error = [], False, "", ""
        self._listed.connect(self._on_listed)
        self._removed.connect(self._on_removed)

    apps = Property("QVariantList", lambda self: self._apps, notify=changed)
    loaded = Property(bool, lambda self: self._loaded, notify=changed)
    busy = Property(str, lambda self: self._busy, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)

    @Slot()
    def refresh(self):
        def work():
            try:
                self._listed.emit(list_apps())
            except Exception as e:  # noqa: BLE001 - no libflatpak: an empty list, not a crash
                log.warning("listing the apps: %s", e)
                self._listed.emit([])
        threading.Thread(target=work, daemon=True).start()

    def _on_listed(self, apps):
        self._apps, self._loaded = apps, True
        self.changed.emit()

    @Slot(str)
    def open(self, app_id):
        if APP_ID.match(app_id):
            subprocess.Popen(["flatpak", "run", app_id], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str, str, bool)
    def remove(self, ref, scope, delete_data):
        if self._busy:
            return
        self._busy, self._error = ref, ""
        self.changed.emit()
        threading.Thread(target=lambda: self._removed.emit(ref, *remove(ref, scope, delete_data)),
                         daemon=True).start()

    def _on_removed(self, ref, ok, error):
        self._busy = ""
        name = next((a["name"] for a in self._apps if a["ref"] == ref), ref)
        self._error = "" if ok else name
        self.changed.emit()
        self.refresh()

    @Slot()
    def getMore(self):
        """Sloth Welcome: the apps to choose from (nothing is preinstalled, the user picks there)."""
        try:
            subprocess.Popen(["sloth-welcome"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("sloth-welcome: %s", e)
