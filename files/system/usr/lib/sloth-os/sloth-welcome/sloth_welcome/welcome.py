"""Controller of the welcome wizard (QML <-> Python)."""
import grp
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from sloth_common import sharing, windows_import

from . import catalog, desktop, i18n
from .i18n import tr
from .installer import Installer

log = logging.getLogger("sloth-welcome")


def _size_text(nbytes):
    if nbytes >= 1024**3:
        return f"{nbytes / 1024**3:.1f} GB"
    return f"{max(1, round(nbytes / 1024**2))} MB" if nbytes else "0 MB"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os"
DONE_MARKER = CONFIG_DIR / "welcome-done"
# Where the wizard is (if the machine restarts meanwhile, it continues from there); deleted at the end
PROGRESS = CONFIG_DIR / "welcome-progress.json"

# The StackLayout pages in QML. The categories share one page,
# the order of steps: welcome, appearance, passwords, sharing, one step per category, installing, done.
STEAM = "com.valvesoftware.Steam"  # not preinstalled: can be chosen in the Games step

PAGE_WELCOME, PAGE_LOOK, PAGE_CATEGORY, PAGE_INSTALL, PAGE_DONE, PAGE_SECURITY, PAGE_SHARING, PAGE_WINDOWS = range(8)


def build_steps(windows_only=False):
    """The sequence of steps. The Windows step (bringing files over) is only there if the machine has a Windows partition;
    windows_only: only this one step (sloth-welcome --windows-import, from Sloth Center's Disks page)."""
    if windows_only:
        return ["windows"]
    return (["welcome", "look", "security", "sharing"] + (["windows"] if windows_import.candidates() else [])
            + [f"cat{i}" for i in range(len(catalog.CATEGORIES))] + ["install", "done"])

# Passwords: with the "only for risky things" choice these need no password (also adjustable per topic on Sloth
# Center's Account and security page; sloth-helper admin-policy saves it)
HELPER = "/usr/libexec/sloth-os/sloth-helper"
EASY_TOPICS = ["software", "updates", "network", "datetime", "services"]


# sloth-exe prints this when the install is done but the installer still runs (e.g. the EA app installer does not exit
# while the EA app runs): the queue then moves on, and sloth-exe waits for the installer's end in the background
QUEUED_DONE = "sloth-exe: queued-done"


def _run_queued(path):
    """One installer in the .exe handler; its exit code (or 0 if sloth-exe reported that it is done)."""
    proc = subprocess.Popen(["sloth-exe", "--queued", str(path)], stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if line.strip() == QUEUED_DONE:
            proc.stdout.close()
            threading.Thread(target=proc.wait, daemon=True).start()
            return 0
    return proc.wait()


FLATPAK_APP_DIRS = [Path("/var/lib/flatpak/app"), Path.home() / ".local/share/flatpak/app"]


def installed_apps():
    """The catalog apps that are already installed: when the wizard is run again they show with a tick and are not
    installed again (Flatpak: its installed folder; Windows program: the .exe handler's records, with a Start menu entry)."""
    from sloth_common.apps import library, menu
    out = []
    for cat in catalog.CATEGORIES:
        for app in cat["apps"]:
            source = app.get("source", "flathub")
            try:
                if source in ("flathub", "github-bundle"):
                    present = any((d / app["id"] / "current").exists() for d in FLATPAK_APP_DIRS)
                elif source == "windows":
                    found = library.find_installed(app["name"], app["file"])
                    present = found is not None and bool(menu.entries(found))
                else:
                    present = False  # part of the system (e.g. KDE Connect): turning it on may run again
            except Exception:  # noqa: BLE001  a broken entry must not stop the wizard
                log.exception("%s: could not tell whether it is installed", app["id"])
                present = False
            if present:
                out.append(app["id"])
    return out


def apply_language():
    """Window title and text direction for the chosen language (Arabic, Hebrew: right to left, mirrored)."""
    QApplication.setApplicationDisplayName(tr("app.title"))
    QApplication.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl()
                                    else Qt.LayoutDirection.LeftToRight)


class WelcomeController(QObject):
    changed = Signal()
    # Signals from the installer's thread (Qt moves them to the main thread)
    _status_sig = Signal(str, str, int)
    _app_sig = Signal(str, str, str)
    _done_sig = Signal(object, object)

    _win_sig = Signal(object)   # from the Windows step's background thread: the updated state
    _queue_done_sig = Signal(object)  # the Windows programs' install queue finished: [(name, exit code)]
    hideRequested = Signal()    # the window hides while the Windows programs install
    showRequested = Signal()    # and comes back at the end

    def __init__(self, parent=None, windows_only=False):
        super().__init__(parent)
        self._windows_only = windows_only
        self._steps = build_steps(windows_only)
        self._step = 0
        self._selected = []
        # When run again, the current appearance should be selected (on first start the factory default)
        self._scheme = desktop.current_color_scheme() or "SlothSilverDark"
        self._layout = desktop.current_layout() or "windows10"
        self._present = installed_apps()  # what is already installed: ticked, not installed again
        self._status = ""
        self._detail = ""
        self._progress = -1
        self._app_states = {}
        self._summary = ""          # translation key
        self._failures = []         # [(name, error key)]
        self._online = desktop.is_online()
        self._installed = []
        self._security = "all"      # "all" (password for everything) or "recommended"
        self._autologin = False
        self._security_saved = ("all", False)
        # Sharing experiences (sloth_common/sharing.py): "" until chosen, "yes" / "no"
        self._sharing = ("yes" if sharing.enabled() else "no") if sharing.CONFIG.exists() else ""
        self._status_sig.connect(self._on_status)
        self._app_sig.connect(self._on_app_state)
        self._done_sig.connect(self._on_done)
        self._installer = Installer(self._status_sig.emit, self._app_sig.emit, self._done_sig.emit)
        # Windows step: "idle" | "scanning" | "ready" | "copying" | "done" | "locked" | "none" | "failed" | "nospace"
        self._win = {"state": "idle", "users": [], "user": "", "keys": [], "bookmarks": True,
                     "done": 0, "total": 0, "result": {}, "need": 0, "free": 0}
        self._win_mounts = []        # what we mounted (unmounted at the end)
        self._win_cancel = threading.Event()
        self._win_sig.connect(self._on_win)
        # Windows programs (e.g. game launchers): the downloaded installers after the wizard, one by one (sloth-exe --queued)
        self._win_queue = []         # [(name, installer path)]
        self._queue_state = ""       # "" | "running" | "done"
        self._queue_done_sig.connect(self._on_queue_done)
        if windows_only:
            self._start_windows_scan()
        else:
            self._restore()

    # --- Continuing after an interruption (PROGRESS) -----------------------------------

    def _save(self):
        if self._windows_only:
            return
        state = {"step": self._step_name(), "language": i18n.language(), "selected": self._selected,
                 "scheme": self._scheme, "layout": self._layout, "security": self._security,
                 "autologin": self._autologin, "installed": self._installed,
                 "failures": self._failures, "summary": self._summary,
                 "win_queue": [[name, str(path)] for name, path in self._win_queue], "queue": self._queue_state}
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp = PROGRESS.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            tmp.replace(PROGRESS)
        except OSError as e:
            log.warning("saving the state: %s", e)

    def _restore(self):
        """If the previous run did not get to the end (e.g. the machine restarted meanwhile): continues at the same place with the same choices."""
        try:
            state = json.loads(PROGRESS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(state, dict):
            return
        if state.get("language") in {l["code"] for l in i18n.available()}:
            i18n.set_language(state["language"])
            apply_language()
        known = {a["id"] for cat in catalog.CATEGORIES for a in cat["apps"]}
        self._selected = [a for a in state.get("selected", []) if a in known]
        self._scheme = state.get("scheme", self._scheme)
        self._layout = state.get("layout", self._layout)
        if state.get("security") in ("all", "recommended"):
            self._security = state["security"]
        self._autologin = bool(state.get("autologin"))
        step = state.get("step", "")
        if step in self._steps and self._steps.index(step) > self._steps.index("security"):
            self._security_saved = (self._security, self._autologin)  # this was already saved
        if step == "install":
            # interrupted while installing: at the last category, with the same choices; on "Install"
            # the apps already installed are done at once, the rest are installed
            step = f"cat{len(catalog.CATEGORIES) - 1}"
        elif step == "done":
            self._installed = [a for a in state.get("installed", []) if a in known]
            self._failures = [tuple(f) for f in state.get("failures", []) if isinstance(f, list) and len(f) == 2]
            self._summary = state.get("summary", "") or "done.all_ok"
            if state.get("queue") != "done":
                # the Windows installers have not run yet (or it was interrupted meanwhile): offers them again
                self._win_queue = [(name, Path(path)) for name, path in state.get("win_queue", [])
                                   if Path(path).is_file()]
            else:
                self._queue_state = "done"
        if step in self._steps:
            self._step = self._steps.index(step)
            if step == "cat0" or step.startswith("cat"):
                self._online = desktop.is_online()
            if step == "windows":
                self._start_windows_scan()
            log.info("continuing: %s", step)

    # --- Properties ------------------------------------------------------

    def _step_name(self):
        return self._steps[self._step]

    @Property(int, notify=changed)
    def page(self):
        name = self._step_name()
        if name.startswith("cat"):
            return PAGE_CATEGORY
        return {"welcome": PAGE_WELCOME, "look": PAGE_LOOK, "security": PAGE_SECURITY, "sharing": PAGE_SHARING,
                "windows": PAGE_WINDOWS, "install": PAGE_INSTALL, "done": PAGE_DONE}[name]

    @Property(int, notify=changed)
    def categoryIndex(self):
        name = self._step_name()
        return int(name[3:]) if name.startswith("cat") else -1

    @Property(bool, notify=changed)
    def lastCategory(self):
        return self._step_name() == f"cat{len(catalog.CATEGORIES) - 1}"

    @Property(int, constant=True)
    def stepCount(self):
        return max(1, len(self._steps) - 2)  # installing and done are not questions

    @Property(int, notify=changed)
    def stepNumber(self):
        return min(self._step + 1, self.stepCount)

    @Property(bool, constant=True)
    def windowsOnly(self):
        return self._windows_only

    @Property("QVariantList", notify=changed)
    def selectedInCategory(self):
        i = self.categoryIndex
        if i < 0:
            return []
        ids = {a["id"] for a in catalog.CATEGORIES[i]["apps"]}
        return [a for a in self._selected if a in ids]

    # --- Nyelv ---------------------------------------------------------------
    # QML takes the texts from the "strings" map; on a language change every label updates.

    @Property("QVariantList", constant=True)
    def languages(self):
        return i18n.available()

    @Property(str, notify=changed)
    def language(self):
        return i18n.language()

    @Property("QVariantMap", notify=changed)
    def strings(self):
        return i18n.strings()

    @Slot(str)
    def setLanguage(self, code):
        if code != i18n.language():
            i18n.set_language(code)
            apply_language()
            self._save()
            self.changed.emit()

    # --- Lists (in the chosen language) ----------------------------------------

    @Property("QVariantList", notify=changed)
    def categories(self):
        out = []
        for cat in catalog.CATEGORIES:
            apps = [{**a, "summary": tr(f"app.{a['id']}"),
                     "iconUrl": f"file://{catalog.ICON_DIR}/{a['id']}.png"} for a in cat["apps"]]
            out.append({**cat, "name": tr(f"category.{cat['id']}.name"),
                        "hint": tr(f"category.{cat['id']}.hint"), "apps": apps})
        return out

    @Property("QVariantList", notify=changed)
    def schemes(self):
        return [{**s, "name": tr(f"scheme.{s['id']}")} for s in desktop.COLOR_SCHEMES]

    @Property("QVariantList", notify=changed)
    def layouts(self):
        return [{**l, "name": tr(f"layout.{l['id']}.name"), "description": tr(f"layout.{l['id']}.description")}
                for l in desktop.LAYOUTS]

    @Property(str, notify=changed)
    def currentLayout(self):
        return self._layout

    @Property("QVariantList", notify=changed)
    def selectedIds(self):
        return list(self._selected)

    @Property(str, notify=changed)
    def currentScheme(self):
        return self._scheme

    @Property(str, notify=changed)
    def statusText(self):
        return self._status

    @Property(str, notify=changed)
    def detailText(self):
        return self._detail

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property("QVariantMap", notify=changed)
    def appStates(self):
        return dict(self._app_states)

    @Property(str, notify=changed)
    def summaryText(self):
        return tr(self._summary) if self._summary else ""

    @Property("QVariantList", notify=changed)
    def failures(self):
        return [{"name": name, "error": tr(err)} for name, err in self._failures]

    @Property(bool, notify=changed)
    def online(self):
        return self._online

    @Property(bool, notify=changed)
    def steamInstalled(self):
        """The "Sign in to Steam" button is only shown if Steam was installed just now."""
        return STEAM in self._installed

    @Property(bool, notify=changed)
    def hasBrowser(self):
        browsers = {a["id"] for a in catalog.CATEGORIES[0]["apps"]}
        return any(a in browsers for a in self._selected)

    # --- Passwords ------------------------------------------------------------

    @Property(bool, constant=True)
    def isAdmin(self):
        try:
            return os.environ.get("USER", "") in grp.getgrnam("wheel").gr_mem
        except KeyError:
            return False

    @Property(str, notify=changed)
    def securityChoice(self):
        return self._security

    @Property(bool, notify=changed)
    def autologin(self):
        return self._autologin

    @Slot(str)
    def setSecurityChoice(self, choice):
        if choice in ("all", "recommended"):
            self._security = choice
            self.changed.emit()

    @Slot(bool)
    def setAutologin(self, value):
        self._autologin = value
        self.changed.emit()

    @Property(str, notify=changed)
    def sharingChoice(self):
        return self._sharing

    @Slot(str)
    def setSharingChoice(self, choice):
        if choice in ("yes", "no"):
            self._sharing = choice
            self.changed.emit()

    def _save_security(self):
        """Saves the choice (in the background; polkit shows the password window)."""
        wanted = (self._security, self._autologin)
        if wanted == self._security_saved:
            return
        self._security_saved = wanted
        request = json.dumps({"topics": EASY_TOPICS if self._security == "recommended" else [],
                              "sudo": False, "autologin": self._autologin})

        def work():
            try:
                r = subprocess.run(["pkexec", HELPER, "admin-policy"], input=request,
                                   capture_output=True, text=True, timeout=600)
                log.info("password settings: %s", r.stdout.strip() or r.stderr.strip())
            except (OSError, subprocess.SubprocessError) as e:
                log.warning("password settings: %s", e)
        threading.Thread(target=work, daemon=True).start()

    # --- Bringing files over from Windows (sloth_common/windows_import.py) ------------

    @Property(str, notify=changed)
    def windowsState(self):
        return self._win["state"]

    @Property("QVariantList", notify=changed)
    def windowsUsers(self):
        return [u["name"] for u in self._win["users"]]

    @Property(str, notify=changed)
    def windowsUser(self):
        return self._win["user"]

    @Property("QVariantList", notify=changed)
    def windowsFolders(self):
        """The folders of the chosen Windows account: [{key, size (as text), selected}] (without the empty ones)."""
        user = self._win_user()
        if not user:
            return []
        return [{"key": key, "size": _size_text(size), "selected": key in self._win["keys"]}
                for key, size in user["folders"].items() if size]

    @Property(int, notify=changed)
    def windowsBookmarkCount(self):
        user = self._win_user()
        return user["bookmarks"] if user else 0

    @Property(bool, notify=changed)
    def windowsBookmarks(self):
        return self._win["bookmarks"]

    @Property(int, notify=changed)
    def windowsProgress(self):
        total = self._win["total"]
        return int(self._win["done"] * 100 / total) if total else -1

    @Property(str, notify=changed)
    def windowsDetail(self):
        w = self._win
        if w["state"] == "copying":
            return f"{_size_text(w['done'])} / {_size_text(w['total'])}"
        if w["state"] == "nospace":
            return tr("windows.nospace", need=_size_text(w["need"]), free=_size_text(w["free"]))
        if w["state"] == "done":
            r = w["result"]
            text = tr("windows.done", count=r.get("copied", 0) + r.get("skipped", 0))
            if r.get("failed"):
                text += " " + tr("windows.failed_some", count=len(r["failed"]))
            return text
        return ""

    def _win_user(self):
        return next((u for u in self._win["users"] if u["name"] == self._win["user"]), None)

    def _start_windows_scan(self):
        self._win.update(state="scanning")
        self.changed.emit()

        def work():
            found, locked, failed = [], False, False
            for part in windows_import.candidates():
                if part["locked"]:
                    locked = True
                    continue
                mnt, ours = windows_import.mount(part["device"])
                if not mnt:
                    failed = True
                    continue
                users = windows_import.users(mnt)
                if ours:
                    if users:
                        self._win_mounts.append(part["device"])
                    else:
                        windows_import.unmount(part["device"])  # not a Windows system (e.g. a data disk)
                found.extend(users)
            state = "ready" if found else "locked" if locked else "failed" if failed else "none"
            self._win_sig.emit({"state": state, "users": found})

        threading.Thread(target=work, daemon=True).start()

    def _on_win(self, update):
        if "users" in update and update["users"] != self._win["users"]:
            users = update["users"]
            first = users[0] if users else None
            self._win.update(user=first["name"] if first else "",
                             keys=[k for k, size in first["folders"].items() if size] if first else [])
        self._win.update(update)
        self.changed.emit()

    @Slot(str)
    def setWindowsUser(self, name):
        user = next((u for u in self._win["users"] if u["name"] == name), None)
        if user and self._win["state"] == "ready":
            self._win.update(user=name, keys=[k for k, size in user["folders"].items() if size])
            self.changed.emit()

    @Slot(str)
    def toggleWindowsFolder(self, key):
        keys = self._win["keys"]
        if key in keys:
            keys.remove(key)
        else:
            keys.append(key)
        self.changed.emit()

    @Slot(bool)
    def setWindowsBookmarks(self, value):
        self._win["bookmarks"] = value
        self.changed.emit()

    @Slot()
    def startWindowsCopy(self):
        user = self._win_user()
        if not user or self._win["state"] != "ready":
            return
        keys = [k for k in self._win["keys"] if user["folders"].get(k)]
        need = sum(user["folders"][k] for k in keys)
        free = shutil.disk_usage(Path.home()).free
        if need + 1024**3 > free:  # 1 GB headroom
            self._win.update(state="nospace", need=need, free=free)
            self.changed.emit()
            return
        self._win.update(state="copying", done=0, total=need)
        self._win_cancel.clear()
        self.changed.emit()

        def work():
            result = windows_import.copy(
                user["home"], keys, on_progress=lambda done, total, _n: self._win_sig.emit({"done": done, "total": total}),
                cancelled=self._win_cancel.is_set)
            if self._win["bookmarks"] and user["bookmarks"]:
                try:
                    windows_import.export_bookmarks(
                        user["home"], windows_import.target_dir("desktop") / tr("windows.bookmarks_file"))
                except OSError as e:
                    log.warning("bookmarks: %s", e)
            self._win_sig.emit({"state": "done", "result": result})

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def retryWindows(self):
        """After "not enough space": back to choosing."""
        if self._win["state"] == "nospace":
            self._win["state"] = "ready"
            self.changed.emit()

    def release_windows(self):
        self._win_cancel.set()
        for device in self._win_mounts:
            windows_import.unmount(device)
        self._win_mounts = []

    # --- Navigation ----------------------------------------------------------

    @Slot()
    def next(self):
        if self._step_name() == "security":
            self._save_security()
        if self._step_name() == "sharing":
            if not self._sharing:
                return  # a choice is needed (the button is inactive until then)
            sharing.set_enabled(self._sharing == "yes")
        if self._step_name() == "windows":
            if self._win["state"] in ("scanning", "copying"):
                return  # while it works, the button is inactive
            self.release_windows()
            if self._windows_only:
                QApplication.quit()
                return
        if self.lastCategory:
            self.install()
            return
        if self._step_name() not in ("install", "done"):
            self._step += 1
            if self._step_name() == "cat0":
                self._online = desktop.is_online()
            if self._step_name() == "windows" and self._win["state"] == "idle":
                self._start_windows_scan()
            self._save()
            self.changed.emit()

    @Slot()
    def back(self):
        if 0 < self._step and self._step_name() not in ("install", "done"):
            self._step -= 1
            self._save()
            self.changed.emit()

    @Property("QVariantList", constant=True)
    def presentIds(self):
        return list(self._present)

    @Slot(str)
    def toggle(self, app_id):
        if app_id in self._present:
            return
        if app_id in self._selected:
            self._selected.remove(app_id)
        else:
            self._selected.append(app_id)
        self._save()
        self.changed.emit()

    @Slot(str)
    def setScheme(self, scheme_id):
        if scheme_id != self._scheme and desktop.apply_color_scheme(scheme_id):
            self._scheme = scheme_id
            self._save()
            self.changed.emit()

    @Slot(str)
    def setLayout(self, layout_id):
        if layout_id != self._layout and desktop.apply_layout(layout_id):
            self._layout = layout_id
            self._save()
            self.changed.emit()

    @Slot(str)
    def quickAction(self, name):
        desktop.quick_action(name)

    @Slot()
    def recheckOnline(self):
        self._online = desktop.is_online()
        self.changed.emit()

    @Slot()
    def openNetworkSettings(self):
        desktop.open_network_settings()

    @Slot()
    def install(self):
        if not self._selected:
            self._summary = "done.nothing_selected"
            self._step = self._steps.index("done")
            self.changed.emit()
            return
        self._step = self._steps.index("install")
        self._status = tr("install.preparing")
        self._app_states = {a: "waiting" for a in self._selected}
        self._save()
        self.changed.emit()
        self._installer.start(self._selected)

    @Property(bool, notify=changed)
    def anyInstalled(self):
        return bool(self._installed)

    @Property(bool, notify=changed)
    def pendingWindows(self):
        """There are downloaded Windows installers that have not run yet: no restart at the end, these come first."""
        return bool(self._win_queue) and self._queue_state == ""

    @Property(bool, notify=changed)
    def windowsQueueDone(self):
        return self._queue_state == "done"

    @Property("QVariantList", notify=changed)
    def pendingWindowsNames(self):
        return [name for name, _path in self._win_queue]

    @Slot()
    def runWindowsQueue(self):
        """The Windows programs' installers one by one in the .exe handler; meanwhile the window waits hidden and comes back at the end."""
        if not self.pendingWindows:
            return
        self._queue_state = "running"
        self._save()  # "running": if it is interrupted meanwhile, it offers them again on the next start
        self.hideRequested.emit()

        def work():
            results = []
            for name, path in self._win_queue:
                try:
                    code = _run_queued(path)
                except OSError as e:
                    log.warning("sloth-exe %s: %s", path, e)
                    code = -1
                results.append((name, code))
            self._queue_done_sig.emit(results)

        threading.Thread(target=work, daemon=True).start()

    def _on_queue_done(self, results):
        self._queue_state = "done"
        self._summary = "done.windows_finished"
        self._save()
        self.changed.emit()
        self.showRequested.emit()

    @Slot(bool)
    def finish(self, restart=False):
        self.release_windows()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DONE_MARKER.touch()
        PROGRESS.unlink(missing_ok=True)
        if self._installed and not restart:
            desktop.refresh_app_cache()
        # The installed browsers and Steam go on the taskbar. An already present browser too
        # (without internet the installer copies the live system's Firefox)
        browsers = [a["id"] for a in catalog.CATEGORIES[0]["apps"]]
        present = [a for a in browsers if Path("/var/lib/flatpak/app", a).is_dir()]
        desktop.pin_to_taskbar([a for a in self._installed if a in browsers or a == STEAM]
                               + [a for a in present if a not in self._installed])
        if restart:
            desktop.reboot()
        QApplication.quit()

    # --- The installer's signals -------------------------------------------------

    def _on_status(self, text, detail, pct):
        self._status, self._detail, self._progress = text, detail, pct
        self.changed.emit()

    def _on_app_state(self, app_id, state, _error):
        self._app_states[app_id] = state
        self.changed.emit()

    def _on_done(self, ok, failed):
        downloads = self._installer.windows_installers
        self._win_queue = [((catalog.find_app(a) or {}).get("name", a), downloads[a]) for a in ok if a in downloads]
        self._installed = list(ok)
        self._failures = [((catalog.find_app(a) or {}).get("name", a), err) for a, err in failed.items()]
        if not failed:
            self._summary = "done.all_ok"
        elif ok:
            self._summary = "done.some_failed"
        else:
            self._summary = "done.all_failed"
        self._progress = 100
        self._step = self._steps.index("done")
        self._save()
        self.changed.emit()
