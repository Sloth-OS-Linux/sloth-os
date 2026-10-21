"""Installed Windows programs: list, start, files, repair, move, remove, and taking over programs installed
elsewhere (Steam, Lutris, Bottles, an earlier install).

Where programs live and their data are in the shared sloth_common.apps (the .exe handler uses it too):
by default ~/Applications/<program>/. Installing and starting is done by the .exe handler (sloth-exe); this page
calls it. No administrator rights are needed: everything is in the user's own folder.
"""
import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot

from sloth_common import sharing
from sloth_common.apps import imports, library, menu, packages

from .i18n import N_, tr

log = logging.getLogger("sloth-center.winprograms")

# Where a program can be taken over from (brand names are not translated; for an earlier plain-Wine install the word
# "Wine" does not appear)
SOURCE_LABELS = {"steam": "Steam", "lutris": "Lutris", "bottles": "Bottles", "wine": N_("Earlier Windows programs")}


def _source_label(source):
    label = SOURCE_LABELS.get(source, source)
    return tr(label) if source == "wine" else label


def _size_text(nbytes):
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2)):
        if nbytes >= div:
            v = nbytes / div
            return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + f" {unit}"
    return tr("less than 1 MB")


def _dir_size(path):
    """The folder's size; links (e.g. "Program files") are not counted twice."""
    total = 0
    for dirpath, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def _pretty(path):
    """~/Applications instead of /home/<name>/Applications."""
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


class WinProgramsController(QObject):
    changed = Signal()
    _sizes_ready = Signal(object)
    _others_ready = Signal(object)
    _work_done = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._sizes = {}
        self._busy = False
        self._message = ""
        self._others = []
        self._sizes_ready.connect(self._on_sizes)
        self._others_ready.connect(self._on_others)
        self._work_done.connect(self._on_work_done)
        self.refresh()

    @Property("QVariantList", notify=changed)
    def programs(self):
        return [{**p, "size": self._sizes.get(p["id"], "")} for p in self._items]

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(str, notify=changed)
    def location(self):
        """New programs are installed here."""
        return _pretty(library.default_library())

    @Property("QVariantList", notify=changed)
    def otherPrograms(self):
        """Programs installed elsewhere (Steam, Lutris, Bottles, an earlier install) that we have not taken over yet."""
        return self._others

    @Property(bool, notify=changed)
    def sharing(self):
        """Sharing with the shared knowledge (sloth_exe/community.py): an anonymous report of the settings that worked."""
        return sharing.enabled()

    @Slot(bool)
    def setSharing(self, value):
        sharing.set_enabled(value)
        self.changed.emit()

    @Slot()
    def refresh(self):
        # From the old location (~/.local/share/sloth-os/windows-programs) we bring them into the new library once
        try:
            library.migrate_legacy()
        except OSError as e:
            log.warning("migration: %s", e)
        items = []
        default = library.default_library()
        apps = library.all_apps()
        for app in apps:
            entries = menu.entries(app)
            icon = next((e["icon"] for e in entries if e["icon"].startswith("/")), "")
            meta = app.meta
            installer = meta.get("installer", "")
            items.append({
                "id": app.id, "name": app.name, "kind": app.kind,
                "entries": [{"name": e["name"], "target": e["target"]} for e in entries],
                "icon": f"file://{icon}" if icon else "",
                "folder": _pretty(app.dir),
                "source": _source_label((meta.get("source") or {}).get("from", "")),
                "publisher": meta.get("publisher", ""),
                "shared": app.id == library.SHARED_ID,
                "canReinstall": bool(installer) and Path(installer).is_file(),
                "hasFiles": app.kind in ("windows", "appimage"),
                "canMove": app.kind in ("windows", "appimage") and not app.legacy and app.dir.parent != default,
            })
        self._items = items
        self.changed.emit()
        # Computing the size and searching for programs installed elsewhere can be slow: on a background thread
        dirs = {a.id: a.dir for a in apps}
        threading.Thread(target=lambda: self._sizes_ready.emit(
            {k: _size_text(_dir_size(d)) for k, d in dirs.items()}), daemon=True).start()
        threading.Thread(target=lambda: self._others_ready.emit(
            [{"key": f.key, "name": f.name, "source": _source_label(f.source), "canLink": imports.can_link(f),
              "canAdopt": imports.can_adopt(f)} for f in imports.found()]), daemon=True).start()

    def _on_others(self, others):
        self._others = others
        self.changed.emit()

    def _on_sizes(self, sizes):
        self._sizes = sizes
        self.changed.emit()

    def _app(self, app_id):
        app = library.find(app_id)
        if app is None:
            log.warning("no such program: %s", app_id)
        return app

    def _set_message(self, text):
        self._message = text
        self.changed.emit()

    def _run_in_background(self, work):
        """A long operation (remove, move, take over) on a background thread; at the end a message and a refresh."""
        self._busy = True
        self.changed.emit()

        def run():
            try:
                text = work()
            except Exception as e:  # an error must not hang the interface
                log.warning("operation: %s", e)
                text = tr("That didn't work. Please try again later.")
            self._work_done.emit(text or "")

        threading.Thread(target=run, daemon=True).start()

    def _on_work_done(self, text):
        self._busy = False
        self._message = text
        self.refresh()

    # --- Actions ---------------------------------------------------------------------------------

    @Slot(str)
    def install(self, url):
        """Installing from a chosen .exe / .msi file (done by the .exe handler, as on a double-click)."""
        path = QUrl(url).toLocalFile() if "://" in url else url
        if path:
            subprocess.Popen(["sloth-exe", path], start_new_session=True)

    @Slot(str)
    def launch(self, app_id):
        app = self._app(app_id)
        if app is None:
            return
        cmd = {"link": imports.launch_command, "box": packages.box_launch_command,
               "appimage": lambda a: ["sloth-exe", "--run", a.id]}.get(app.kind)
        if cmd:
            if cmd(app):
                subprocess.Popen(cmd(app), start_new_session=True, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            return
        target = next((e["target"] for e in menu.entries(app) if e["target"]), None)
        if target:
            subprocess.Popen(["sloth-exe", "--launch", app.id, target], start_new_session=True)
        else:
            self.editShortcuts(app_id)

    @Slot(str)
    def openFolder(self, app_id):
        """The program's folder in Dolphin (with "Program files" holding the installed files)."""
        app = self._app(app_id)
        if app is not None:
            subprocess.Popen(["xdg-open", str(app.dir)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str)
    def editShortcuts(self, app_id):
        """The .exe handler's edit window: what should be in the Start menu (the possible launchers recognized)."""
        app = self._app(app_id)
        if app is None or app.kind != "windows":
            return
        proc = subprocess.Popen(["sloth-exe", "--shortcuts", app.id])
        threading.Thread(target=lambda: (proc.wait(), self._work_done.emit("")), daemon=True).start()

    @Slot(str)
    def repair(self, app_id):
        """Repair: deletes the remembered start settings; on the next start it looks for a working one again."""
        app = self._app(app_id)
        if app is None or app.kind != "windows":
            return
        if app.busy():
            self._set_message(tr("{name} is running right now. Close it, then try again.", name=app.name))
            return
        app.save_meta(launch={})
        self._set_message(tr("Done. The next time it starts, {name} will look for the settings that work for it again.",
                             name=app.name))

    @Slot(str)
    def reinstall(self, app_id):
        """Reinstalls into the same folder (the settings and saves stay)."""
        app = self._app(app_id)
        installer = (app.meta.get("installer") if app else "") or ""
        if installer and Path(installer).is_file():
            subprocess.Popen(["sloth-exe", installer], start_new_session=True)

    @Slot(str)
    def remove(self, app_id):
        """The program, its Start menu entries and its log."""
        app = self._app(app_id)
        if app is None:
            return
        if app.busy():
            self._set_message(tr("{name} is running right now. Close it, then try again.", name=app.name))
            return
        name = app.name
        self._items = [p for p in self._items if p["id"] != app_id]

        def work():
            # a package installed in a box: first out of the box (and the Start menu) too
            if app.kind == "box" and not packages.box_uninstall(app):
                return tr("{name} can't be removed from here.", name=name)
            return "" if library.remove(app) else tr("{name} can't be removed from here.", name=name)

        self._run_in_background(work)

    @Slot(str)
    def setLocation(self, url):
        """Where new programs go (e.g. another drive). The existing ones stay, and can be moved one by one."""
        path = Path(QUrl(url).toLocalFile() if "://" in url else url)
        if not library.supported_location(path):
            self._set_message(tr("This drive uses a Windows format (NTFS, exFAT or FAT). Programs can't be installed "
                                 "here; choose a Linux drive or folder."))
            return
        library.set_default_library(path)
        self._set_message(tr("New programs will be installed here: {path}", path=_pretty(path)))
        self.refresh()

    @Slot(str)
    def move(self, app_id):
        """Moves it to where new programs go (the Start menu entries stay valid)."""
        app = self._app(app_id)
        if app is None:
            return
        if app.busy():
            self._set_message(tr("{name} is running right now. Close it, then try again.", name=app.name))
            return
        target = library.default_library()
        name = app.name
        self._run_in_background(
            lambda: tr("{name} moved to: {path}", name=name, path=_pretty(target))
            if library.move(app, target) else tr("Moving {name} didn't work. The program stayed where it was and "
                                                 "works there just the same.", name=name))

    @Slot(str, bool)
    def importProgram(self, key, adopt):
        """Adds a program installed elsewhere: with the original app (link), or as its own copy (adopt)."""
        f = imports.find(key)
        if f is None:
            return
        if not adopt:
            imports.link(f)
            self._set_message(tr("{name} is now listed here too, and starts just like before.", name=f.name))
            self.refresh()
            return
        if imports.prefix_in_use(f.prefix):
            self._set_message(tr("{name} is running right now. Close it, then try again.", name=f.name))
            return

        def work():
            if imports.adopt(f, tr("Program files")) is None:
                return tr("Taking over {name} didn't work. Everything stayed as it was in its original place.", name=f.name)
            return tr("{name} has been taken over. From now on it starts on its own; nothing changed in its original place.", name=f.name)

        self._run_in_background(work)
