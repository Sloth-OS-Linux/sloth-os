"""A .exe kezelő ablakának vezérlője.

Állapotok: choose (mit csináljunk?) -> working (előkészítés / telepítés) ->
pick (mi kerüljön a Start menübe?) | running (az ablak elrejtve) | error.
"""
import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import anticheat, backend, diagnose, heal, identify, programs
from .i18n import catalog, tr
from .runner import Runner

log = logging.getLogger("sloth-exe")

# Ennyi másodperc után úgy vesszük, hogy a program rendben elindult (az ablak elrejtőzik)
STARTED_AFTER_S = 8
# Ha ennél hamarabb kilép, lehet, hogy nem indult el rendesen (önjavítás, heal.py)
QUICK_EXIT_S = 20
# Ha eddig fut, a beállítás bevált: megjegyezzük
WORKED_AFTER_S = 45


class ExeController(QObject):
    changed = Signal()
    hideWindow = Signal()
    showWindow = Signal()
    _identified = Signal(object, str)  # a háttérszálból: (GAMEID / "" / None, név)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "choose"
        self._exe = None
        self._name = ""
        self._icon = ""
        self._installer = False
        self._status = ""
        self._progress = -1
        self._error = ""
        self._shortcuts = []
        self._program = None
        self._mode = ""  # "install" | "run"
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
        # Ha az indító kilépett, de a program tovább fut (pl. Battle.net Launcher -> Battle.net), megvárjuk
        self._busy_timer = QTimer(self, interval=5000)
        self._busy_timer.timeout.connect(self._check_busy)
        # Önjavítás (heal.py): a próbálkozások sora erre az indításra
        self._plan = []
        self._attempt = None
        self._tries = 0
        self._snapshot = False      # van-e pillanatkép az indítás előtti állapotról
        self._before_proton = None  # a pillanatképhez tartozó Proton-verzió
        self._succeeded = False
        self._gameid = None

    # --- Belépési pontok -----------------------------------------------------

    def open_file(self, path):
        self._exe = Path(path).resolve()
        self._name = programs.display_name(self._exe)
        if self._name.lower() in ("setup", "install", "installer", ""):
            self._name = tr("misc.program")
        self._installer = programs.looks_like_installer(self._exe)
        icon = programs.extract_icon(self._exe, Path("/tmp") / f"sloth-exe-{programs.slugify(self._name)}.png")
        self._set_icon(icon)
        self._state = "choose"
        self._update_window()
        self.changed.emit()

    def launch(self, slug, rel):
        self._program = programs.Program(slug)
        self._exe = self._program.prefix / rel
        self._name = self._program.meta.get("name") or programs.display_name(self._exe)
        # a Start menü bejegyzéshez már kibontott ikon
        self._set_icon(self._program.icons / f"{programs.slugify(self._exe.stem)}.png")
        self._mode = "run"
        self._update_window()
        if not self._exe.exists():
            self._fail(tr("error.not_found"))
            return
        self._start_run()

    def manage_shortcuts(self, slug):
        """Utólagos szerkesztés: mely .exe-k legyenek a Start menüben (a Sloth Központból)."""
        self._program = programs.Program(slug)
        self._name = self._program.meta.get("name") or slug
        self._mode = "manage"
        found = programs.find_shortcuts(self._program)
        seen = {str(p).lower() for _n, p in found}
        found += [(programs.display_name(p), p) for p in self._program.list_exes()
                  if str(p).lower() not in seen and not any(w in p.name.lower() for w in programs.SKIP_WORDS)]
        self._shortcuts = []
        for name, path in found[:30]:
            icon = programs.extract_icon(path, self._program.icons / f"{programs.slugify(path.stem)}.png")
            self._shortcuts.append({"name": name, "path": str(path),
                                    "checked": programs.desktop_file_path(self._program, path).exists(),
                                    "iconUrl": f"file://{icon}" if icon else ""})
        if not self._shortcuts:
            self._fail(tr("error.no_exe"))
            return
        self._update_window()
        self._state = "pick"
        self.changed.emit()

    # --- Tulajdonságok ---------------------------------------------------------

    state = Property(str, lambda self: self._state, notify=changed)
    name = Property(str, lambda self: self._name, notify=changed)
    iconUrl = Property(str, lambda self: self._icon, notify=changed)
    isInstaller = Property(bool, lambda self: self._installer, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    shortcuts = Property("QVariantList", lambda self: list(self._shortcuts), notify=changed)
    mode = Property(str, lambda self: self._mode, notify=changed)
    strings = Property("QVariantMap", lambda self: catalog.strings(), constant=True)

    # --- Műveletek -------------------------------------------------------------

    @Slot()
    def install(self):
        slug = programs.slugify(self._name)
        base, n = slug, 2
        while programs.Program(slug).exists():
            slug, n = f"{base}-{n}", n + 1
        self._program = programs.Program(slug)
        self._program.save_meta(name=self._name, installer=str(self._exe))
        self._mode = "install"
        self._update_window()
        self._set_working(tr("status.preparing_install", name=self._name))
        self._runner.start(self._program, self._exe)

    @Slot(bool)
    def run(self, add_to_menu):
        self._program = programs.Program(programs.SHARED)
        self._program.save_meta(name=tr("misc.other_programs"))
        if add_to_menu:
            programs.add_to_menu(self._program, self._name, self._exe)
        self._start_run()

    @Slot(int)
    def toggleShortcut(self, index):
        if 0 <= index < len(self._shortcuts):
            self._shortcuts[index] = {**self._shortcuts[index], "checked": not self._shortcuts[index]["checked"]}
            self.changed.emit()

    @Slot()
    def confirmShortcuts(self):
        for s in self._shortcuts:
            desktop = programs.desktop_file_path(self._program, Path(s["path"]))
            if s["checked"] and not desktop.exists():
                programs.add_to_menu(self._program, s["name"], Path(s["path"]))
            elif not s["checked"] and desktop.exists():
                desktop.unlink()
        QApplication.quit()

    @Slot()
    def close(self):
        QApplication.quit()

    # --- Belső -------------------------------------------------------------------

    def _start_run(self):
        found = anticheat.detect(self._exe)
        self._anticheat = found
        if found and not found[1]:
            # Ismerten Linux-ellenes csalásvédelem: ne próbálkozzunk hiába
            self._fail(anticheat.blocked_text(self._name, found[0]))
            return
        self._mode = "run"
        self._update_window()
        self._set_working(tr("status.starting", name=self._name))
        rec = heal.record(self._program, self._exe)
        if rec.get("gameid") is not None:
            self._on_identified(rec["gameid"], rec.get("title", ""))
            return
        # Melyik program ez? (az umu adatbázisa, ha kell a Steam áruháza; egyszer, a háttérben)
        exe, name = self._exe, self._name
        threading.Thread(target=lambda: self._identified.emit(*self._identify(exe, name)), daemon=True).start()

    @staticmethod
    def _identify(exe, name):
        try:
            return identify.identify(exe, name, online=backend.online())
        except Exception as e:  # a felismerés hibája ne akadályozza az indítást
            log.warning("felismerés: %s", e)
            return None, ""

    def _on_identified(self, gameid, title):
        rec = heal.record(self._program, self._exe)
        if gameid is not None and rec.get("gameid") != gameid:
            rec.update(gameid=gameid, title=title)
            heal.save_record(self._program, self._exe, rec)
            if gameid:
                log.info("felismerve: %s (%s)", title, gameid)
        self._gameid = gameid or None
        self._plan = heal.plan(self._program, self._exe)
        self._tries = 0
        self._snapshot = False
        self._succeeded = False
        self._next_attempt()

    def _next_attempt(self):
        """A terv következő próbája (a pillanatkép nélkül nem biztonságos Proton-váltások kimaradnak)."""
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
        self._runner.start(self._program, self._exe, attempt, self._gameid)
        self._started_timer.start()
        self._worked_timer.start()

    def _set_icon(self, path):
        self._icon = f"file://{path}" if path and Path(path).is_file() else ""

    def _update_window(self):
        """Ablakcím és tálcaikon: "XY indítása" / "XY telepítése", a program saját ikonjával."""
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

    def _fail(self, text):
        self._state = "error"
        self._error = text
        self.showWindow.emit()
        self.changed.emit()

    def _on_status(self, key, pct):
        self._status = tr(key)
        self._progress = pct
        self._started_timer.start()  # amíg előkészítünk, ne rejtsük el az ablakot
        self.changed.emit()

    def _on_setup_done(self):
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
        self._worked_timer.stop()
        log.info("kilépett: kód=%s, %.0f mp", code, elapsed)
        if code == 127 and elapsed == 0:
            self._fail(tr("error.runtime_missing"))
            return
        if self._mode == "install":
            self._after_install()
            return
        if self._attempt and not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.resolved_name(self._attempt))
        if self._succeeded or elapsed >= QUICK_EXIT_S:
            self._on_worked()
            QApplication.quit()
            return
        if heal.prefix_busy(self._program):
            # Az indító átadta a helyét: a program fut tovább, ez nem hiba
            log.info("az indító kilépett, a program tovább fut")
            self._busy_timer.start()
            self._worked_timer.start()
            return
        lines = self._runner.lines()
        rec = heal.record(self._program, self._exe)
        if code == 0 and rec.get("good") and not diagnose.crashed(lines):
            # Eddig is működött, most sem omlott össze: a felhasználó zárta be
            QApplication.quit()
            return
        if self._anticheat or self._runner.uses_wine:
            # A csalásvédelmen nem segít más beállítás; a tartalék Wine-nál nincs mit váltani
            self._give_up()
            return
        self._heal(rec, lines)

    def _heal(self, rec, lines):
        """Nem indult el rendesen: diagnózis, és ha kell, a következő beállítás. A felhasználó csak „Indítás…”-t lát."""
        attempt = self._attempt
        known = [tuple(f) for f in rec.get("fixes", [])]
        new = [f for f in diagnose.fixes(lines) if f not in known]
        if self._tries >= heal.MAX_ATTEMPTS + 2:
            self._give_up()
            return
        if new:
            # Felismert hiba: ugyanezzel a beállítással, a javítással együtt még egyszer
            log.info("felismert hibák: %s", new)
            rec["fixes"] = [list(f) for f in known + new]
            heal.save_record(self._program, self._exe, rec)
            attempt.fixes = known + new
            self._retry(attempt)
            return
        log.info("nem indult el ezzel: %s", attempt.key)
        failed = set(rec.get("failed", [])) | {f"{heal.resolved_name(attempt)}|{attempt.profile}", attempt.key}
        rec["failed"] = sorted(failed)
        good = rec.get("good")
        if good and f"{good['proton']}|{good['profile']}" in failed:
            rec.pop("good")
        heal.save_record(self._program, self._exe, rec)
        if self._snapshot and heal.restore_snapshot(self._program):
            # vissza az indítás előtti állapotra (és verzióra); a következő próbához új pillanatkép kell
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
        """A program rendben fut: megjegyezzük, mi működött, és a pillanatkép törölhető."""
        if self._succeeded or self._mode != "run" or not self._attempt or self._runner.uses_wine:
            return
        self._succeeded = True
        rec = heal.record(self._program, self._exe)
        name = heal.resolved_name(self._attempt)
        if rec.get("good") != {"proton": name, "profile": self._attempt.profile}:
            log.info("bevált beállítás: %s|%s", name, self._attempt.profile)
        rec["good"] = {"proton": name, "profile": self._attempt.profile}
        rec["failed"] = [k for k in rec.get("failed", []) if k not in (f"{name}|{self._attempt.profile}",
                                                                       self._attempt.key)]
        heal.save_record(self._program, self._exe, rec)
        self._program.save_meta(prefix_proton=name)
        if self._snapshot:
            heal.drop_snapshot(self._program)
            self._snapshot = False

    def _check_busy(self):
        if not heal.prefix_busy(self._program):
            self._busy_timer.stop()
            self._worked_timer.stop()
            QApplication.quit()

    def _on_verb_done(self, verb, code):
        if code == 0:
            verbs = sorted(set(self._program.meta.get("verbs", [])) | {verb})
            self._program.save_meta(verbs=verbs)
        else:
            log.warning("összetevő telepítése nem sikerült: %s (%s)", verb, code)

    def _after_install(self):
        # A telepítő a legfrissebb Protonnal futott: ezen a verzión áll a program mappája
        if not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.newest() or "auto")
        found = programs.find_shortcuts(self._program)
        if not found:
            # Nincs parancsikon: a telepített .exe-k közül választhat
            found = [(programs.display_name(p), p) for p in self._program.list_exes()
                     if not any(w in p.name.lower() for w in programs.SKIP_WORDS)][:12]
            checked = len(found) == 1
        else:
            checked = True
        if not found:
            self._fail(tr("error.nothing_installed"))
            return
        self._shortcuts = []
        for name, path in found:
            icon = programs.extract_icon(path, self._program.icons / f"{programs.slugify(path.stem)}.png")
            self._shortcuts.append({"name": name, "path": str(path), "checked": checked,
                                    "iconUrl": f"file://{icon}" if icon else ""})
        self._state = "pick"
        self.showWindow.emit()
        self.changed.emit()
