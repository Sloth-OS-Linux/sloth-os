"""Controller of the .exe handler's window.

States: choose (what should we do?) -> working (preparing / installing) ->
pick (what goes into the Start menu?) | done (installed, can be started) | running (window hidden) | error.

Besides Windows programs it also handles Linux packages (AppImage, .deb, .rpm), and gives a clear message for
Mac files (sloth_common.apps.packages).

Where programs live, their data and Start menu entries are in the shared sloth_common.apps
(Sloth Center uses it too); here there is only running and the interface.
"""
import logging
import re
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sloth_common.apps import detect, library, menu, native, packages

from . import anticheat, backend, community, diagnose, heal, identify, quirks
from .i18n import catalog, tr
from .runner import Runner

log = logging.getLogger("sloth-exe")

# After this many seconds we consider the program properly started (the window hides)
STARTED_AFTER_S = 8
# If it exits sooner than this, it may not have started properly (self-healing, heal.py)
QUICK_EXIT_S = 20
# If it runs this long, the setting worked: we remember it
WORKED_AFTER_S = 45
# After the installer exits, we wait this long for its other processes (e.g. the actual installer
# started by a downloader) to finish too
INSTALL_SETTLE_S = 3
# If preparing the installation gives no sign of life for this long, a reassuring text (so nobody thinks it froze)
SLOW_PREP_S = 60
# When started from the queue (--queued), this tells Sloth Welcome that we are done, if we wait for the installer's end in the background
QUEUED_DONE = "sloth-exe: queued-done"
# At most this many files are looked at in the install folder (a game folder can be huge)
MAX_INSTALL_FILES = 5000
# Error reporters that may start during an install (e.g. BlizzardError.exe): they do not mean the program runs
ERROR_REPORTER = re.compile(r"(?i)error|crash|report")


def _program_exes(found):
    """The .exe names that mean "the installed program runs": the launchers found, and every other .exe in the install
    folder except helpers (updaters, agents, crash reporters…). Battle.net's launcher hands over to its client right away,
    so the client counts too: the install is done as soon as its login window is up."""
    names = {c.path.name.lower() for c in found.candidates}
    if found.install_dir and Path(found.install_dir).is_dir():
        for i, path in enumerate(Path(found.install_dir).rglob("*")):
            if i >= MAX_INSTALL_FILES:
                break
            if path.suffix.lower() == ".exe" and not (detect.HELPER_EXE.search(path.name)
                                                      or ERROR_REPORTER.search(path.name)):
                names.add(path.name.lower())
    return names


class ExeController(QObject):
    changed = Signal()
    hideWindow = Signal()
    showWindow = Signal()
    _identified = Signal(object, str, str)  # from the background thread: (GAMEID / "" / None, name, fingerprint)
    _package_done = Signal(object)          # from the background thread: the installed AppImage (App) or None
    _flathub_found = Signal(object)         # from the background thread: the program's Flathub version, or None

    def __init__(self, parent=None, queued=False):
        super().__init__(parent)
        self._queued = queued  # from Sloth Welcome's install queue (--queued)
        self._state = "choose"
        self._exe = None
        self._name = ""
        self._icon = ""
        self._installer = False
        self._status = ""
        self._progress = -1
        self._error = ""
        self._error_icon = "dialog-warning"
        self._shortcuts = []
        self._program = None   # library.App
        self._existing = None  # if we already installed this program (library.find_installed)
        self._unfinished = None  # the folder of an unfinished install: the new install goes here, no duplicate
        self._baseline = None  # before installing: what was already in the program's environment (detect.baseline)
        self._sure = True      # whether it became certain after the install what the program starts with
        self._mode = ""  # "install" | "run" | "manage"
        self._join = False     # something already runs in the program's environment: we join it
        self._installer_alive = False  # the install is done, but the installer still runs (_check_install_done)
        self._closing = False  # we are only waiting for the installer to exit (_quit)
        self._anticheat = None
        self._runner = Runner(self)
        self._runner.status.connect(self._on_status)
        self._runner.setup_done.connect(self._on_setup_done)
        self._runner.finished.connect(self._on_finished)
        self._runner.verb_done.connect(self._on_verb_done)
        self._started_timer = QTimer(self, singleShot=True, interval=STARTED_AFTER_S * 1000)
        self._started_timer.timeout.connect(self._on_probably_started)
        self._worked_timer = QTimer(self, singleShot=True, interval=WORKED_AFTER_S * 1000)
        self._worked_timer.timeout.connect(self._on_worked)
        self._identified.connect(self._on_identified)
        self._package_done.connect(self._on_appimage_installed)
        self._flathub_found.connect(self._on_flathub)
        self._flathub = None     # the Linux package's Flathub version: {"id", "name", "summary"}
        self._native_reason = ""  # for a Windows installer: why we recommend the Linux version (native.py)
        self._kind = "windows"   # the kind of the opened file (packages.kind_of), or "windows"
        self._done_text = ""
        self._start_cmd = None   # the Start command in the "done" state
        self._box_steps = []
        self._box_lines = []
        self._box_proc = None
        # If the launcher exited but the program keeps running (e.g. Battle.net Launcher -> Battle.net), we wait for it
        self._busy_timer = QTimer(self, interval=5000)
        self._busy_timer.timeout.connect(self._check_busy)
        # Installing: after the installer exits, its other processes should finish too
        self._install_timer = QTimer(self, interval=INSTALL_SETTLE_S * 1000)
        self._install_timer.timeout.connect(self._check_install_done)
        self._slow_timer = QTimer(self, singleShot=True, interval=SLOW_PREP_S * 1000)
        self._slow_timer.timeout.connect(self._on_slow_prep)
        # Self-healing (heal.py): the sequence of attempts for this start
        self._plan = []
        self._attempt = None
        self._tries = 0
        self._snapshot = False      # whether there is a snapshot of the state before the start
        self._before_proton = None  # the Proton version belonging to the snapshot
        self._succeeded = False
        self._gameid = None
        self._key = ""

    # --- Entry points -----------------------------------------------------

    def open_file(self, path):
        library.migrate_legacy()
        self._exe = Path(path).resolve()
        if self._exe.suffix.lower() not in (".exe", ".msi"):
            kind = packages.kind_of(self._exe)
            if kind:
                self._open_package(kind)
                return
        self._name = detect.display_name(self._exe)
        if self._name.lower() in ("setup", "install", "installer", ""):
            self._name = tr("misc.program")
        self._installer = detect.looks_like_installer(self._exe)
        # A program is installed only once: if it is already there, open it or reinstall into the same place
        found = library.find_installed(self._name, self._exe) if self._installer else None
        # Unfinished install (the installer did not run to the end, only the folder was created): not "already installed",
        # but the new install goes into the same folder. A finished install has a Start menu entry, or
        # data saved after recognition (uninstall_key)
        finished = found is not None and (menu.entries(found) or "uninstall_key" in found.meta)
        self._existing = found if finished else None
        self._unfinished = None if finished else found
        # A popular program with a version made for Linux (e.g. Teams, Discord, Epic -> Heroic): we recommend that,
        # its Windows installation stays next to it (if it is already installed, we do not interfere)
        linux = native.match(self._exe.name) if self._existing is None else None
        if linux:
            log.info("Linux version: %s (%s)", linux["id"], linux["reason"])
            self._flathub = {"id": linux["id"], "name": linux["name"], "summary": ""}
            self._native_reason = linux["reason"]
        icon = menu.extract_icon(self._exe, Path("/tmp") / f"sloth-exe-{library.slugify(self._name)}.png")
        self._set_icon(icon)
        self._state = "choose"
        self._update_window()
        self.changed.emit()

    def launch(self, app_id, target):
        """Starting from the Start menu. target: the start file (relative to the environment, or a full path)."""
        library.migrate_legacy()
        self._program = library.find(app_id)
        if self._program is None:
            self._name = app_id
            self._fail(tr("error.not_found"))
            return
        self._exe = self._program.prefix / target
        self._name = self._program.name if app_id != library.SHARED_ID else detect.display_name(self._exe)
        # the icon already extracted for the Start menu entry
        self._set_icon(menu.icon_path(self._program, self._exe))
        # The client instead of a short-lived launcher (otherwise the runner would stop with it); self-healing
        # adatai is a klienshez tartoznak
        self._exe = quirks.launch_target(self._exe)
        self._mode = "run"
        self._update_window()
        if not self._exe.exists():
            self._fail(tr("error.not_found"))
            return
        running = library.running_exes(self._program)
        if self._exe.name.lower() in running:
            # Already running: we say so instead of restarting (otherwise the start would wait for the previous one to end)
            self._info(tr("info.already_running", name=self._name))
            return
        # Another program runs in the same environment (e.g. the launcher, and now the user starts a
        # game): we join it, without self-healing, so the running program is not disturbed
        self._join = bool(running)
        self._start_run()

    def missing(self, app_id):
        """The program started from the Start menu is missing (e.g. its folder was deleted)."""
        app = library.find(app_id)
        self._name = app.name if app else app_id
        self._mode = "run"
        self._update_window()
        self._fail(tr("error.not_found"))

    def manage_shortcuts(self, app_id):
        """Editing afterwards: which .exe files should be in the Start menu (from Sloth Center)."""
        library.migrate_legacy()
        self._program = library.find(app_id)
        if self._program is None:
            self._fail(tr("error.not_found"))
            return
        self._name = self._program.name
        self._mode = "manage"
        self._shortcuts = [self._shortcut_item(c.name, c.path, menu.desktop_file_path(self._program, c.path).exists())
                           for c in detect.launch_candidates(self._program)]
        self._sure = True
        self._update_window()
        self._state = "pick"
        self.changed.emit()

    # --- Properties ---------------------------------------------------------

    state = Property(str, lambda self: self._state, notify=changed)
    name = Property(str, lambda self: self._name, notify=changed)
    iconUrl = Property(str, lambda self: self._icon, notify=changed)
    isInstaller = Property(bool, lambda self: self._installer, notify=changed)
    alreadyInstalled = Property(bool, lambda self: self._existing is not None, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    errorIcon = Property(str, lambda self: self._error_icon, notify=changed)
    shortcuts = Property("QVariantList", lambda self: list(self._shortcuts), notify=changed)
    mode = Property(str, lambda self: self._mode, notify=changed)
    fileKind = Property(str, lambda self: self._kind, notify=changed)
    doneText = Property(str, lambda self: self._done_text, notify=changed)
    canStart = Property(bool, lambda self: self._start_cmd is not None, notify=changed)
    flathubName = Property(str, lambda self: (self._flathub or {}).get("name", ""), notify=changed)
    nativeReason = Property(str, lambda self: self._native_reason, notify=changed)
    sure = Property(bool, lambda self: self._sure, notify=changed)
    anyChecked = Property(bool, lambda self: any(s["checked"] for s in self._shortcuts), notify=changed)
    strings = Property("QVariantMap", lambda self: catalog.strings(), constant=True)

    @Property(str, notify=changed)
    def browseFolder(self):
        """The browser's starting folder: the program's install location, if known."""
        if not self._program:
            return ""
        folder = self._program.windows_to_host(self._program.meta.get("install_dir", "")) \
            or self._program.prefix / "drive_c"
        return QUrl.fromLocalFile(str(folder)).toString()

    # --- Actions -------------------------------------------------------------

    @Slot()
    def install(self):
        if self._kind != "windows":
            self._install_package()
            return
        # Reinstalling into the existing folder: the Start menu entries stay the same, no duplicates
        self._program = self._existing or self._unfinished or library.create(self._name, installer=str(self._exe))
        self._program.save_meta(installer=str(self._exe))
        self._baseline = detect.baseline(self._program)
        self._mode = "install"
        self._update_window()
        self._set_working(tr("status.preparing_install", name=self._name))
        self._slow_timer.start()
        self._start_runner(self._program, self._exe)
        # we already watch while the installer runs (_check_install_done)
        self._install_timer.start()

    @Slot()
    def openExisting(self):
        """Starts the already installed program, as from the Start menu; if it has no entry, the user can choose."""
        entries = menu.entries(self._existing)
        target = next((e["target"] for e in entries if e["target"]), None)
        if target:
            self.launch(self._existing.id, target)
        else:
            self.manage_shortcuts(self._existing.id)

    @Slot(bool)
    def run(self, add_to_menu):
        self._program = library.shared_app(tr("misc.other_programs"))
        if add_to_menu:
            menu.add(self._program, self._name, self._exe)
        self._start_run()

    @Slot(int)
    def toggleShortcut(self, index):
        if 0 <= index < len(self._shortcuts):
            self._shortcuts[index] = {**self._shortcuts[index], "checked": not self._shortcuts[index]["checked"]}
            self.changed.emit()

    @Slot(str)
    def addFile(self, url):
        """The file chosen in the browser (if recognition did not find what the program starts with)."""
        path = Path(QUrl(url).toLocalFile() if "://" in url else url)
        if path.suffix.lower() != ".exe" or not path.is_file():
            return
        for i, s in enumerate(self._shortcuts):
            if Path(s["path"]) == path:
                self._shortcuts[i] = {**s, "checked": True}
                break
        else:
            self._shortcuts.insert(0, self._shortcut_item(detect.display_name(path), path, True))
        self.changed.emit()

    @Slot(bool)
    def confirmShortcuts(self, start=False):
        first = None
        # .exe files with the same name (e.g. from the EA app's linked and versioned folders) get the same entry:
        # an unticked row must not delete what a ticked one just created
        wanted = {menu.desktop_file_path(self._program, Path(s["path"])) for s in self._shortcuts if s["checked"]}
        for s in self._shortcuts:
            path = Path(s["path"])
            desktop = menu.desktop_file_path(self._program, path)
            if s["checked"]:
                if not desktop.exists():
                    menu.add(self._program, s["name"], path)
                first = first or path
            elif desktop.exists() and desktop not in wanted:
                desktop.unlink()
        icon = next((e["icon"] for e in menu.entries(self._program) if e["icon"].startswith("/")), None)
        self._program.set_folder_icon(icon)
        if start and first:
            if self._queued or self._installer_alive:
                # the next installer in the queue comes (or the installer still runs, and this instance waits for it):
                # the program starts in a separate process, this instance exits
                subprocess.Popen(["sloth-exe", "--launch", self._program.id, str(menu.target(self._program, first))],
                                 start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._quit()
                return
            # "Start": starts right away, as later from the Start menu
            self._existing = None
            self.launch(self._program.id, menu.target(self._program, first))
            return
        self._quit()

    @Slot()
    def close(self):
        self._quit()

    def _quit(self):
        """Quitting. If the installer still runs (at the end it started the installed program, e.g. the EA app, and it
        does not exit until then), we do not interrupt it: the window disappears, and we quit when the installer ends. When
        started from the queue (Welcome), we report that we are done, so the queue does not wait until the user closes the program."""
        if not (self._installer_alive and self._runner.running()):
            QApplication.quit()
            return
        self._closing = True
        self.hideWindow.emit()
        if self._queued:
            print(QUEUED_DONE, flush=True)

    @Slot()
    def startInstalled(self):
        """In the "done" state: starts the freshly installed program."""
        if self._start_cmd:
            subprocess.Popen(self._start_cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QApplication.quit()

    @Slot()
    def searchDiscover(self):
        """Searches Discover for the program's Linux (Flatpak) version."""
        subprocess.Popen(["plasma-discover", "--search", self._name], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QApplication.quit()

    @Slot()
    def installFromDiscover(self):
        """The program's Flathub version in Discover (fits better, and Discover updates it)."""
        if self._flathub:
            subprocess.Popen(["plasma-discover", f"appstream://{self._flathub['id']}"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        QApplication.quit()

    @Slot()
    def runOnly(self):
        """AppImage without installing: make it executable and start it."""
        try:
            self._exe.chmod(self._exe.stat().st_mode | 0o100)
            subprocess.Popen([str(self._exe)], start_new_session=True, cwd=str(self._exe.parent))
        except OSError as e:
            log.warning("running AppImage: %s", e)
            self._fail(tr("error.not_started", name=self._name))
            return
        QApplication.quit()

    # --- Linux packages and Mac files --------------------------------------------

    def _open_package(self, kind):
        self._kind = kind
        self._name = packages.display_name(self._exe)
        self._installer = kind in ("appimage", "deb", "rpm")
        self._existing = self._unfinished = None
        self._set_icon(None)
        self._update_window()
        if kind == "mac":
            self._info(tr("package.mac", name=self._name))
            return
        if kind == "mac-script":
            self._info(tr("package.mac_script"))
            return
        self._state = "choose"
        self.changed.emit()
        # If it is on Flathub too, we recommend that (we search in the background; the interface stays usable)
        name = self._name
        threading.Thread(target=lambda: self._flathub_found.emit(
            packages.flathub_match(name) if backend.online() else None), daemon=True).start()

    def _on_flathub(self, found):
        self._flathub = found
        self.changed.emit()

    def _install_package(self):
        self._mode = "install"
        self._update_window()
        self._set_working(tr("status.installing", name=self._name))
        if self._kind == "appimage":
            exe = self._exe
            threading.Thread(target=lambda: self._package_done.emit(packages.install_appimage(exe)),
                             daemon=True).start()
            return
        self._box_steps = packages.box_steps(self._kind, self._exe, packages.box_exists(self._kind))
        self._box_lines = []
        self._next_box_step()

    def _on_appimage_installed(self, app):
        if app is None:
            self._fail(tr("error.package_failed", name=self._name))
            return
        self._name = app.name
        self._set_icon(next((e["icon"] for e in menu.entries(app) if e["icon"].startswith("/")), None))
        self._finish_package(tr("package.installed", name=app.name), ["sloth-exe", "--run", app.id])

    def _next_box_step(self):
        key, cmd = self._box_steps.pop(0)
        # the first time, creating the box (download) can take minutes
        self._status = tr("status.first_setup") if key != "box.install" else tr("status.installing", name=self._name)
        self.changed.emit()
        self._box_proc = QProcess(self)
        self._box_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._box_proc.readyReadStandardOutput.connect(self._read_box)
        self._box_proc.finished.connect(self._on_box_step)
        log.info("installing package: %s", key)
        self._box_proc.start(cmd[0], cmd[1:])

    def _read_box(self):
        for line in bytes(self._box_proc.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
            if line.strip():
                self._box_lines.append(line.strip())
                log.info("%s", line.strip())

    def _on_box_step(self, code, _status):
        if code != 0:
            self._fail(tr("error.package_failed", name=self._name))
            return
        if self._box_steps:
            self._next_box_step()
            return
        package, apps = packages.parse_box_output(self._box_lines)
        app = packages.record_box_install(self._kind, self._exe, package, apps)
        if not apps:
            self._finish_package(tr("package.installed_no_app", name=self._name), None)
            return
        self._name = app.name
        self._finish_package(tr("package.installed", name=app.name), packages.box_launch_command(app))

    def _finish_package(self, text, start_cmd):
        self._done_text = text
        self._start_cmd = start_cmd
        self._state = "done"
        self._update_window()
        self.showWindow.emit()
        self.changed.emit()

    # --- Internals -------------------------------------------------------------------

    def _shortcut_item(self, name, path, checked):
        icon = menu.extract_icon(path, menu.icon_path(self._program, path))
        return {"name": name, "path": str(path), "checked": checked, "iconUrl": f"file://{icon}" if icon else ""}

    def _start_run(self):
        found = anticheat.detect(self._exe)
        self._anticheat = found
        if found and not found[1]:
            # Known anti-Linux anti-cheat: do not try in vain
            self._fail(anticheat.blocked_text(self._name, found[0]))
            return
        self._mode = "run"
        self._update_window()
        self._set_working(tr("status.starting", name=self._name))
        if self._join:
            # Joining the already running environment: with the setting that worked, without attempts
            rec = heal.record(self._program, self._exe)
            good = rec.get("good")
            attempt = heal.Attempt(None if not good or good["proton"] == "auto" else good["proton"],
                                   good["profile"] if good else "default", [tuple(f) for f in rec.get("fixes", [])])
            self._attempt = attempt
            self._start_runner(self._program, self._exe, attempt, rec.get("gameid") or None, join=True)
            self._started_timer.start()
            return
        rec = heal.record(self._program, self._exe)
        if rec.get("gameid") is not None and rec.get("key"):
            self._on_identified(rec["gameid"], rec.get("title", ""), rec["key"])
            return
        # Which program is this? (the umu database, if needed the Steam store; once, in the background)
        exe, name = self._exe, self._name
        threading.Thread(target=lambda: self._identified.emit(*self._identify(exe, name)), daemon=True).start()

    @staticmethod
    def _identify(exe, name):
        try:
            key = community.program_key(exe, identify.candidates(exe, name))
            return (*identify.identify(exe, name, online=backend.online()), key)
        except Exception as e:  # a recognition error must not prevent the start
            log.warning("recognition: %s", e)
            return None, "", ""

    def _on_identified(self, gameid, title, key):
        rec = heal.record(self._program, self._exe)
        if (gameid is not None and rec.get("gameid") != gameid) or (key and rec.get("key") != key):
            if gameid is not None:
                rec.update(gameid=gameid, title=title)
            if key:
                rec["key"] = key
            heal.save_record(self._program, self._exe, rec)
            if gameid:
                log.info("felismerve: %s (%s)", title, gameid)
        if gameid and not self._program.meta.get("is_game") and self._program.id != library.SHARED_ID:
            # Recognized game: goes among the Games in the Start menu
            self._program.save_meta(is_game=True)
            menu.set_category(self._program)
        self._gameid = gameid or None
        self._key = key
        self._plan = heal.plan(self._program, self._exe, community.suggestion(key, gameid) if key or gameid else None)
        self._tries = 0
        self._snapshot = False
        self._succeeded = False
        self._next_attempt()

    def _next_attempt(self):
        """The plan's next attempt (Proton switches that are unsafe without a snapshot are skipped)."""
        while self._plan:
            attempt = self._plan.pop(0)
            if heal.needs_snapshot(self._program, attempt) and not self._snapshot:
                self._before_proton = heal.prefix_proton(self._program)
                self._snapshot = heal.can_snapshot(self._program) and heal.take_snapshot(self._program)
            if not self._snapshot and not heal.allowed_without_snapshot(self._program, attempt):
                continue
            self._run_attempt(attempt)
            return True
        return False

    def _run_attempt(self, attempt):
        self._attempt = attempt
        self._tries += 1
        self._start_runner(self._program, self._exe, attempt, self._gameid)
        self._started_timer.start()
        self._worked_timer.start()

    def _set_icon(self, path):
        self._icon = f"file://{path}" if path and Path(path).is_file() else ""

    def _update_window(self):
        """Window title and taskbar icon: "Starting XY" / "Installing XY", with the program's own icon."""
        if self._mode == "manage":
            key = "title.manage"
        elif self._mode == "install" or (self._installer and not self._mode):
            key = "title.install"
        else:
            key = "title.launch"
        QApplication.setApplicationDisplayName(tr(key, name=self._name))
        QApplication.setWindowIcon(QIcon(self._icon.removeprefix("file://")) if self._icon
                                   else QIcon.fromTheme("sloth-os"))

    def _set_working(self, text):
        self._state = "working"
        self._status = text
        self._progress = -1
        self.changed.emit()

    def _start_runner(self, *args, **kwargs):
        # An unexpected error here must not leave the window spinning forever: error page, details in the log
        try:
            self._runner.start(*args, **kwargs)
        except Exception:
            log.exception("starting the runner failed")
            self._fail(tr("error.not_started", name=self._name))

    def _fail(self, text):
        self._slow_timer.stop()
        self._state = "error"
        self._error = text
        self._error_icon = "dialog-warning"
        self.showWindow.emit()
        self.changed.emit()

    def _info(self, text):
        self._state = "error"
        self._error = text
        self._error_icon = "dialog-information"
        self.showWindow.emit()
        self.changed.emit()

    def _on_status(self, key, pct):
        self._status = tr(key)
        self._progress = pct
        self._started_timer.start()  # while we prepare, do not hide the window
        if self._slow_timer.isActive():
            self._slow_timer.start()
        self.changed.emit()

    def _on_slow_prep(self):
        if self._mode == "install" and self._state == "working":
            self._status = tr("status.still_working")
            self.changed.emit()

    def _on_setup_done(self):
        self._slow_timer.stop()
        if self._mode == "install":
            self._status = tr("status.finish_in_installer")
        else:
            self._status = tr("status.starting", name=self._name)
        self._progress = -1
        self.changed.emit()

    def _on_probably_started(self):
        if self._mode == "install":
            self._on_setup_done()
        elif self._runner.running():
            self._state = "running"
            self.changed.emit()
            self.hideWindow.emit()

    def _on_finished(self, code, elapsed):
        self._started_timer.stop()
        self._slow_timer.stop()
        self._worked_timer.stop()
        log.info("exited: code=%s, %.0f s", code, elapsed)
        if self._installer_alive:
            self._installer_alive = False
            if not self._closing:
                return  # the installer exited; the user is still working in this window
            # the install was already done, we were only waiting for the installer's end (_quit)
            QApplication.quit()
            return
        if code == 127 and elapsed == 0:
            self._fail(tr("error.runtime_missing"))
            return
        if self._mode == "install":
            # The installer exited; downloaders and multi-stage installers may still be working
            self._status = tr("status.finish_in_installer")
            self.changed.emit()
            self._install_timer.start()
            return
        if self._join:
            # Joined start: we do not repair the running environment, we do not overwrite anything
            QApplication.quit()
            return
        if self._attempt and not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.resolved_name(self._attempt))
        if self._succeeded or elapsed >= QUICK_EXIT_S:
            # With an error code, after a short run (e.g. Battle.net after 30 s, code 3) we do not remember it as a
            # setting that "worked"; we do not restart it either, because maybe the user closed it
            if self._succeeded or code == 0 or elapsed >= WORKED_AFTER_S:
                self._on_worked()
            else:
                log.info("exited with an error code (%s), not remembered as a working setting", code)
            QApplication.quit()
            return
        if self._program.busy():
            # The launcher handed over: the program keeps running, this is not an error
            log.info("the launcher exited, the program keeps running")
            self._busy_timer.start()
            self._worked_timer.start()
            return
        lines = self._runner.lines()
        rec = heal.record(self._program, self._exe)
        if code == 0 and rec.get("good") and not diagnose.crashed(lines):
            # It worked before and did not crash now either: the user closed it
            QApplication.quit()
            return
        if self._anticheat or self._runner.uses_wine:
            # A different setting does not help against anti-cheat; with the fallback Wine there is nothing to switch
            self._give_up()
            return
        self._heal(rec, lines)

    def _heal(self, rec, lines):
        """It did not start properly: diagnosis and, if needed, the next setting. The user only sees "Starting…"."""
        attempt = self._attempt
        known = [tuple(f) for f in rec.get("fixes", [])]
        new = [f for f in diagnose.fixes(lines) if f not in known]
        if self._tries >= heal.MAX_ATTEMPTS + 2:
            self._give_up()
            return
        if new:
            # Recognized error: once more with the same setting, together with the fix
            log.info("recognized errors: %s", new)
            rec["fixes"] = [list(f) for f in known + new]
            heal.save_record(self._program, self._exe, rec)
            attempt.fixes = known + new
            self._retry(attempt)
            return
        log.info("did not start with: %s", attempt.key)
        community.queue_report(self._key, attempt, "failed")
        failed = set(rec.get("failed", [])) | {f"{heal.resolved_name(attempt)}|{attempt.profile}", attempt.key}
        rec["failed"] = sorted(failed)
        good = rec.get("good")
        if good and f"{good['proton']}|{good['profile']}" in failed:
            rec.pop("good")
        heal.save_record(self._program, self._exe, rec)
        if self._snapshot and heal.restore_snapshot(self._program):
            # back to the state (and version) before the start; the next attempt needs a new snapshot
            self._program.save_meta(prefix_proton=self._before_proton)
            self._snapshot = False
        for a in self._plan:
            a.fixes = [tuple(f) for f in rec.get("fixes", [])]
        if not self._next_attempt():
            self._give_up()

    def _retry(self, attempt):
        self._plan.insert(0, attempt)
        self._set_working(tr("status.starting", name=self._name))
        self.showWindow.emit()
        if not self._next_attempt():
            self._give_up()

    def _give_up(self):
        if self._snapshot:
            heal.restore_snapshot(self._program)
            self._program.save_meta(prefix_proton=self._before_proton)
            self._snapshot = False
        if self._anticheat:
            self._fail(anticheat.maybe_text(self._name, self._anticheat[0]))
        else:
            self._fail(tr("error.not_started", name=self._name))

    def _on_worked(self):
        """The program runs fine: we remember what worked, and the snapshot can be deleted."""
        if self._succeeded or self._mode != "run" or self._join or not self._attempt or self._runner.uses_wine:
            return
        self._succeeded = True
        rec = heal.record(self._program, self._exe)
        name = heal.resolved_name(self._attempt)
        if rec.get("good") != {"proton": name, "profile": self._attempt.profile}:
            log.info("working setting: %s|%s", name, self._attempt.profile)
        rec["good"] = {"proton": name, "profile": self._attempt.profile}
        rec["failed"] = [k for k in rec.get("failed", []) if k not in (f"{name}|{self._attempt.profile}",
                                                                       self._attempt.key)]
        # Only a new result goes to the shared knowledge (we do not report the same thing on every start)
        reported = f"{name}|{self._attempt.profile}|{sorted(map(list, self._attempt.fixes))}"
        if rec.get("reported") != reported:
            community.queue_report(self._key, self._attempt, "worked")
            rec["reported"] = reported
        heal.save_record(self._program, self._exe, rec)
        self._program.save_meta(prefix_proton=name)
        if self._snapshot:
            heal.drop_snapshot(self._program)
            self._snapshot = False

    def _check_busy(self):
        if not self._program.busy():
            self._busy_timer.stop()
            self._worked_timer.stop()
            QApplication.quit()

    def _on_verb_done(self, verb, code):
        if code == 0:
            verbs = sorted(set(self._program.meta.get("verbs", [])) | {verb})
            self._program.save_meta(verbs=verbs)
        else:
            log.warning("installing a component failed: %s (%s)", verb, code)

    def _check_install_done(self):
        """The install is done when nothing runs in the program's environment any more, or when the installer
        has exited and the program is certainly there (many installers start the program by themselves at the end,
        e.g. Battle.net: we do not wait until the user closes it). It is also done when the installer still
        runs but the installed program has already started (_program_exes): the EA app installer does not exit while the
        EA app runs, and the Battle.net installer stays open while its client already shows the login window."""
        running = library.running_exes(self._program)
        if self._runner.running():
            if self._state != "working" or not self._runner.main_running():
                return
            if running and self._status != tr("status.finish_in_installer"):
                # The installer already runs on the Windows side: preparation is over (even if nothing had
                # to be downloaded, so the runner did not report it); the "still working…" text must not stay up
                self._on_setup_done()
            others = running - {self._exe.name.lower()}
            if not others:
                return
            found = detect.detect(self._program, self._baseline, fallback_name=self._name)
            if not (found.sure and others & _program_exes(found)):
                return
            log.info("the installer still runs, but the installed program has already started: %s", sorted(others))
            self._installer_alive = True
        elif running and (self._exe.name.lower() in running
                          or not detect.detect(self._program, self._baseline, fallback_name=self._name).sure):
            return
        self._install_timer.stop()
        self._after_install()

    def _after_install(self):
        # The installer ran with the latest Proton: the program's folder is on this version
        if not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.newest() or "auto")
        before = self._baseline
        found = detect.detect(self._program, before, fallback_name=self._name)
        if not found.candidates:
            # When reinstalling (or if the installer only updated) there are no new files: from the whole environment
            before = None
            found = detect.detect(self._program, before, fallback_name=self._name)
        log.info("installed: %s (%s), launchers: %s", found.name or self._name, found.install_dir,
                 [(c.name, c.path.name, c.score) for c in found.candidates])
        if not found.candidates:
            self._fail(tr("error.nothing_installed"))
            return
        info = {"publisher": found.publisher, "version": found.version, "uninstall_key": found.uninstall_key}
        if found.install_dir:
            info["install_dir"] = self._program.host_to_windows(found.install_dir) or ""
        self._program.save_meta(**info)
        # The program's real name from Windows' own registry (e.g. "Battle.net", not "Battle Net Setup")
        if found.name and found.name != self._program.name:
            self._program = library.rename(self._program, found.name)
            self._name = found.name
            found = detect.detect(self._program, before, fallback_name=self._name)
        self._program.link_files(self._program.windows_to_host(self._program.meta.get("install_dir", "")),
                                 tr("misc.program_files"))
        self._sure = found.sure
        self._shortcuts = [self._shortcut_item(c.name, c.path, c.checked) for c in found.candidates]
        self._update_window()
        self._state = "pick"
        self.showWindow.emit()
        self.changed.emit()
