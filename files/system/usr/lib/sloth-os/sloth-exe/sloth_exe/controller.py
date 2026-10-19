"""A .exe kezelő ablakának vezérlője.

Állapotok: choose (mit csináljunk?) -> working (előkészítés / telepítés) ->
pick (mi kerüljön a Start menübe?) | running (az ablak elrejtve) | error | info.

A programok helye, adatai és Start menü bejegyzései a közös sloth_common.apps-ban vannak
(a Sloth Központ is azt használja); itt csak a futtatás és a felület.
"""
import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sloth_common.apps import detect, library, menu

from . import anticheat, backend, community, diagnose, heal, identify, quirks
from .i18n import catalog, tr
from .runner import Runner

log = logging.getLogger("sloth-exe")

# Ennyi másodperc után úgy vesszük, hogy a program rendben elindult (az ablak elrejtőzik)
STARTED_AFTER_S = 8
# Ha ennél hamarabb kilép, lehet, hogy nem indult el rendesen (önjavítás, heal.py)
QUICK_EXIT_S = 20
# Ha eddig fut, a beállítás bevált: megjegyezzük
WORKED_AFTER_S = 45
# A telepítő kilépése után ennyi ideig várjuk, hogy a többi folyamata (pl. a letöltő által
# indított tényleges telepítő) is végezzen
INSTALL_SETTLE_S = 3


class ExeController(QObject):
    changed = Signal()
    hideWindow = Signal()
    showWindow = Signal()
    _identified = Signal(object, str, str)  # a háttérszálból: (GAMEID / "" / None, név, ujjlenyomat)

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
        self._error_icon = "dialog-warning"
        self._shortcuts = []
        self._program = None   # library.App
        self._existing = None  # ha ezt a programot már telepítettük (library.find_installed)
        self._baseline = None  # telepítés előtt: mi volt már a program környezetében (detect.baseline)
        self._sure = True      # a telepítés után biztosan kiderült-e, mivel indul
        self._mode = ""  # "install" | "run" | "manage"
        self._join = False     # a program környezetében már fut valami: ahhoz csatlakozunk
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
        # Telepítés: a telepítő kilépése után a többi folyamata is végezzen
        self._install_timer = QTimer(self, interval=INSTALL_SETTLE_S * 1000)
        self._install_timer.timeout.connect(self._check_install_done)
        # Önjavítás (heal.py): a próbálkozások sora erre az indításra
        self._plan = []
        self._attempt = None
        self._tries = 0
        self._snapshot = False      # van-e pillanatkép az indítás előtti állapotról
        self._before_proton = None  # a pillanatképhez tartozó Proton-verzió
        self._succeeded = False
        self._gameid = None
        self._key = ""

    # --- Belépési pontok -----------------------------------------------------

    def open_file(self, path):
        library.migrate_legacy()
        self._exe = Path(path).resolve()
        self._name = detect.display_name(self._exe)
        if self._name.lower() in ("setup", "install", "installer", ""):
            self._name = tr("misc.program")
        self._installer = detect.looks_like_installer(self._exe)
        # Egy programot csak egyszer telepítünk: ha már megvan, megnyitás vagy újratelepítés ugyanoda
        self._existing = library.find_installed(self._name, self._exe) if self._installer else None
        icon = menu.extract_icon(self._exe, Path("/tmp") / f"sloth-exe-{library.slugify(self._name)}.png")
        self._set_icon(icon)
        self._state = "choose"
        self._update_window()
        self.changed.emit()

    def launch(self, app_id, target):
        """Indítás a Start menüből. target: az indítófájl (a környezethez képest relatív, vagy teljes út)."""
        library.migrate_legacy()
        self._program = library.find(app_id)
        if self._program is None:
            self._name = app_id
            self._fail(tr("error.not_found"))
            return
        self._exe = self._program.prefix / target
        self._name = self._program.name if app_id != library.SHARED_ID else detect.display_name(self._exe)
        # a Start menü bejegyzéshez már kibontott ikon
        self._set_icon(menu.icon_path(self._program, self._exe))
        # Rövid életű indító helyett a kliens (a futtató különben vele együtt leállna); az önjavítás
        # adatai is a klienshez tartoznak
        self._exe = quirks.launch_target(self._exe)
        self._mode = "run"
        self._update_window()
        if not self._exe.exists():
            self._fail(tr("error.not_found"))
            return
        running = library.running_exes(self._program)
        if self._exe.name.lower() in running:
            # Már fut: újraindítás helyett szólunk (különben az indítás az előző végéig várna)
            self._info(tr("info.already_running", name=self._name))
            return
        # Más program fut ugyanebben a környezetben (pl. az indító, és most egy játékot indít a
        # felhasználó): ahhoz csatlakozunk, önjavítás nélkül, hogy a futó programot ne zavarjuk
        self._join = bool(running)
        self._start_run()

    def manage_shortcuts(self, app_id):
        """Utólagos szerkesztés: mely .exe-k legyenek a Start menüben (a Sloth Központból)."""
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

    # --- Tulajdonságok ---------------------------------------------------------

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
    sure = Property(bool, lambda self: self._sure, notify=changed)
    anyChecked = Property(bool, lambda self: any(s["checked"] for s in self._shortcuts), notify=changed)
    strings = Property("QVariantMap", lambda self: catalog.strings(), constant=True)

    @Property(str, notify=changed)
    def browseFolder(self):
        """A tallózó kezdőmappája: a program telepítési helye, ha ismert."""
        if not self._program:
            return ""
        folder = self._program.windows_to_host(self._program.meta.get("install_dir", "")) \
            or self._program.prefix / "drive_c"
        return QUrl.fromLocalFile(str(folder)).toString()

    # --- Műveletek -------------------------------------------------------------

    @Slot()
    def install(self):
        # Újratelepítés a meglévő mappába: a Start menü bejegyzései ugyanazok maradnak, nem duplázódnak
        self._program = self._existing or library.create(self._name, installer=str(self._exe))
        self._program.save_meta(installer=str(self._exe))
        self._baseline = detect.baseline(self._program)
        self._mode = "install"
        self._update_window()
        self._set_working(tr("status.preparing_install", name=self._name))
        self._runner.start(self._program, self._exe)

    @Slot()
    def openExisting(self):
        """A már telepített program indítása, ahogy a Start menüből; ha nincs bejegyzése, választhat."""
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
        """A tallózóból választott fájl (ha a felismerés nem találta el, mivel indul a program)."""
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
        for s in self._shortcuts:
            path = Path(s["path"])
            desktop = menu.desktop_file_path(self._program, path)
            if s["checked"]:
                if not desktop.exists():
                    menu.add(self._program, s["name"], path)
                first = first or path
            elif desktop.exists():
                desktop.unlink()
        icon = next((e["icon"] for e in menu.entries(self._program) if e["icon"].startswith("/")), None)
        self._program.set_folder_icon(icon)
        if start and first:
            # „Indítás”: rögtön elindul, ahogy később a Start menüből
            self._existing = None
            self.launch(self._program.id, menu.target(self._program, first))
            return
        QApplication.quit()

    @Slot()
    def close(self):
        QApplication.quit()

    # --- Belső -------------------------------------------------------------------

    def _shortcut_item(self, name, path, checked):
        icon = menu.extract_icon(path, menu.icon_path(self._program, path))
        return {"name": name, "path": str(path), "checked": checked, "iconUrl": f"file://{icon}" if icon else ""}

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
        if self._join:
            # Csatlakozás a már futó környezethez: a bevált beállítással, próbálkozások nélkül
            rec = heal.record(self._program, self._exe)
            good = rec.get("good")
            attempt = heal.Attempt(None if not good or good["proton"] == "auto" else good["proton"],
                                   good["profile"] if good else "default", [tuple(f) for f in rec.get("fixes", [])])
            self._attempt = attempt
            self._runner.start(self._program, self._exe, attempt, rec.get("gameid") or None, join=True)
            self._started_timer.start()
            return
        rec = heal.record(self._program, self._exe)
        if rec.get("gameid") is not None and rec.get("key"):
            self._on_identified(rec["gameid"], rec.get("title", ""), rec["key"])
            return
        # Melyik program ez? (az umu adatbázisa, ha kell a Steam áruháza; egyszer, a háttérben)
        exe, name = self._exe, self._name
        threading.Thread(target=lambda: self._identified.emit(*self._identify(exe, name)), daemon=True).start()

    @staticmethod
    def _identify(exe, name):
        try:
            key = community.program_key(exe, identify.candidates(exe, name))
            return (*identify.identify(exe, name, online=backend.online()), key)
        except Exception as e:  # a felismerés hibája ne akadályozza az indítást
            log.warning("felismerés: %s", e)
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
            # Felismert játék: a Start menüben a Játékok közé kerül
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
            # A telepítő kilépett; a letöltők és a többlépcsős telepítők ilyenkor még dolgozhatnak
            self._status = tr("status.finish_in_installer")
            self.changed.emit()
            self._install_timer.start()
            return
        if self._join:
            # Csatlakozott indítás: a futó környezetet nem javítjuk, nem írunk felül semmit
            QApplication.quit()
            return
        if self._attempt and not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.resolved_name(self._attempt))
        if self._succeeded or elapsed >= QUICK_EXIT_S:
            self._on_worked()
            QApplication.quit()
            return
        if self._program.busy():
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
        community.queue_report(self._key, attempt, "failed")
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
        if self._succeeded or self._mode != "run" or self._join or not self._attempt or self._runner.uses_wine:
            return
        self._succeeded = True
        rec = heal.record(self._program, self._exe)
        name = heal.resolved_name(self._attempt)
        if rec.get("good") != {"proton": name, "profile": self._attempt.profile}:
            log.info("bevált beállítás: %s|%s", name, self._attempt.profile)
        rec["good"] = {"proton": name, "profile": self._attempt.profile}
        rec["failed"] = [k for k in rec.get("failed", []) if k not in (f"{name}|{self._attempt.profile}",
                                                                       self._attempt.key)]
        # A közös tudásnak csak az új eredmény megy (minden indításkor ugyanazt nem jelentjük)
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
            log.warning("összetevő telepítése nem sikerült: %s (%s)", verb, code)

    def _check_install_done(self):
        """A telepítés akkor kész, amikor a program környezetében már semmi nem fut."""
        if self._program.busy():
            return
        self._install_timer.stop()
        self._after_install()

    def _after_install(self):
        # A telepítő a legfrissebb Protonnal futott: ezen a verzión áll a program mappája
        if not self._runner.uses_wine:
            self._program.save_meta(prefix_proton=heal.newest() or "auto")
        before = self._baseline
        found = detect.detect(self._program, before, fallback_name=self._name)
        if not found.candidates:
            # Újratelepítésnél (vagy ha a telepítő csak frissített) nincs új fájl: az egész környezetből
            before = None
            found = detect.detect(self._program, before, fallback_name=self._name)
        log.info("telepítve: %s (%s), indítók: %s", found.name or self._name, found.install_dir,
                 [(c.name, c.path.name, c.score) for c in found.candidates])
        if not found.candidates:
            self._fail(tr("error.nothing_installed"))
            return
        info = {"publisher": found.publisher, "version": found.version, "uninstall_key": found.uninstall_key}
        if found.install_dir:
            info["install_dir"] = self._program.host_to_windows(found.install_dir) or ""
        self._program.save_meta(**info)
        # A Windows saját nyilvántartásából a program valódi neve (pl. „Battle.net”, nem „Battle Net Setup”)
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
