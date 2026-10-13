"""A .exe kezelő ablakának vezérlője.

Állapotok: choose (mit csináljunk?) -> working (előkészítés / telepítés) ->
pick (mi kerüljön a Start menübe?) | running (az ablak elrejtve) | error.
"""
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from . import programs
from .runner import Runner

log = logging.getLogger("sloth-exe")

# Ennyi másodperc után úgy vesszük, hogy a program rendben elindult
STARTED_AFTER_S = 8
GENERIC_ICON = "application-x-ms-dos-executable"


class ExeController(QObject):
    changed = Signal()
    hideWindow = Signal()
    showWindow = Signal()

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
        self._runner = Runner(self)
        self._runner.status.connect(self._on_status)
        self._runner.setup_done.connect(self._on_setup_done)
        self._runner.finished.connect(self._on_finished)
        self._started_timer = QTimer(self, singleShot=True, interval=STARTED_AFTER_S * 1000)
        self._started_timer.timeout.connect(self._on_probably_started)

    # --- Belépési pontok -----------------------------------------------------

    def open_file(self, path):
        self._exe = Path(path).resolve()
        self._name = programs.display_name(self._exe)
        if self._name.lower() in ("setup", "install", "installer", ""):
            self._name = "Program"
        self._installer = programs.looks_like_installer(self._exe)
        icon = programs.extract_icon(self._exe, Path("/tmp") / f"sloth-exe-{programs.slugify(self._name)}.png")
        self._icon = f"file://{icon}" if icon else ""
        self._state = "choose"
        self.changed.emit()

    def launch(self, slug, rel):
        self._program = programs.Program(slug)
        self._exe = self._program.prefix / rel
        self._name = self._program.meta.get("name") or programs.display_name(self._exe)
        if not self._exe.exists():
            self._fail("A programot nem találjuk. Lehet, hogy törölve lett; telepítsd újra.")
            return
        self._start_run()

    # --- Tulajdonságok ---------------------------------------------------------

    state = Property(str, lambda self: self._state, notify=changed)
    name = Property(str, lambda self: self._name, notify=changed)
    iconUrl = Property(str, lambda self: self._icon, notify=changed)
    isInstaller = Property(bool, lambda self: self._installer, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    shortcuts = Property("QVariantList", lambda self: list(self._shortcuts), notify=changed)

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
        self._set_working(f"{self._name} telepítésének előkészítése…")
        self._runner.start(self._program, self._exe, wait_for_exit=True)

    @Slot(bool)
    def run(self, add_to_menu):
        self._program = programs.Program(programs.SHARED)
        self._program.save_meta(name="Egyéb programok")
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
            if s["checked"]:
                programs.add_to_menu(self._program, s["name"], Path(s["path"]))
        QApplication.quit()

    @Slot()
    def close(self):
        QApplication.quit()

    # --- Belső -------------------------------------------------------------------

    def _start_run(self):
        self._mode = "run"
        self._set_working(f"{self._name} indítása…")
        self._runner.start(self._program, self._exe, wait_for_exit=False)
        self._started_timer.start()

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

    def _on_status(self, text, pct):
        self._status = text
        self._progress = pct
        self._started_timer.start()  # amíg előkészítünk, ne rejtsük el az ablakot
        self.changed.emit()

    def _on_setup_done(self):
        if self._mode == "install":
            self._status = "A telepítő ablakában fejezd be a telepítést. Ha végeztél, itt folytatjuk."
        else:
            self._status = f"{self._name} indítása…"
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
        log.info("kilépett: kód=%s, %.0f mp", code, elapsed)
        if code == 127 and elapsed == 0:
            self._fail("A Windows-programok futtatója nincs telepítve. Frissítsd a rendszert a Sloth Központban.")
            return
        if self._mode == "install":
            self._after_install()
            return
        if code != 0 and elapsed < STARTED_AFTER_S:
            self._fail(f"A(z) {self._name} nem indult el. Lehet, hogy ez a program nem működik ezen a "
                       "rendszeren, vagy sérült a fájl.")
            return
        QApplication.quit()

    def _after_install(self):
        found = programs.find_shortcuts(self._program)
        if not found:
            # Nincs parancsikon: a telepített .exe-k közül választhat
            found = [(programs.display_name(p), p) for p in self._program.list_exes()
                     if not any(w in p.name.lower() for w in programs.SKIP_WORDS)][:12]
            checked = len(found) == 1
        else:
            checked = True
        if not found:
            self._fail("Nem találtunk telepített programot. Lehet, hogy a telepítés megszakadt; próbáld újra.")
            return
        self._shortcuts = []
        for name, path in found:
            icon = programs.extract_icon(path, self._program.icons / f"{programs.slugify(path.stem)}.png")
            self._shortcuts.append({"name": name, "path": str(path), "checked": checked,
                                    "iconUrl": f"file://{icon}" if icon else ""})
        self._state = "pick"
        self.showWindow.emit()
        self.changed.emit()
