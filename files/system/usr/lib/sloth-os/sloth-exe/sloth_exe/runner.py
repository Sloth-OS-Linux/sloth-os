"""Windows-program indítása a háttérben (umu-launcher + Proton, tartalékként a rendszer Wine-ja).

A felhasználó a technikai részleteket nem látja: a kimenetből csak emberi
állapotszöveg lesz ("Első indítás előkészítése…"), a többi a naplóba megy.
Hogy melyik futtató indul, azt a backend.py dönti el.
"""
import logging
import re
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal
from PySide6.QtGui import QGuiApplication

from sloth_common import gamesettings

from . import backend

log = logging.getLogger("sloth-exe.runner")

# umu kimenet -> állapot (fordítási kulcs; az első egyező nyer, kisbetűs minták)
_STAGES = [
    (("setting up unified launcher",), "status.first_setup"),
    (("downloading",), "status.downloading"),
    (("extracting",), "status.extracting"),
    (("verifying integrity", "sha256 is ok", "sha512 is ok", "mtree is ok"), "status.verifying"),
    (("updating",), "status.updating"),
    (("restoring runtime",), "status.repairing"),
]
_PERCENT = re.compile(r"(\d{1,3})(?:\.\d+)?\s?%")


class Runner(QObject):
    status = Signal(str, int)   # állapot fordítási kulcsa, százalék (-1 = ismeretlen)
    setup_done = Signal()       # az előkészítés kész, a program elindult
    finished = Signal(int, float)  # kilépési kód, futási idő (mp)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._started_at = 0.0
        self._setup_seen = False
        self._pending = None  # tartalék Wine-nál: (program, args), ami a mappa előkészítése után indul
        self._wrap = []       # játékbeállítások (FPS-kijelző, teljesítmény mód, felskálázás) parancsai

    def start(self, program, exe):
        """program: programs.Program, exe: a futtatandó fájl a gazdagépen."""
        program.prefix.mkdir(parents=True, exist_ok=True)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("WINEPREFIX", str(program.prefix))
        env.insert("GAMEID", program.meta.get("gameid", "umu-default"))
        env.insert("STORE", "none")
        # Mindig megvárjuk, amíg a program összes folyamata kilép. "run" mellett a
        # futtató az első folyamattal együtt leáll, és bezárja, amit az elindított:
        # az indítóprogramok (Battle.net, EA, Epic, Ubisoft) ezért azonnal bezáródnának.
        env.insert("PROTON_VERB", "waitforexitandrun")
        env.insert("WINEDEBUG", "-all")
        # A Wine ne hozzon létre saját menübejegyzéseket: azokat mi kezeljük
        env.insert("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        env.remove("UMU_ZENITY")
        # Játékonkénti beállítások a Sloth Központból (Játékok oldal)
        self._wrap = gamesettings.wrapper(program.meta.get("game"), self._screen())

        self._started_at = time.monotonic()
        if backend.use_wine():
            self._start_wine(program, exe, env)
            return
        # Az .msi telepítőket a Proton magától az msiexec-kel nyitja meg
        log.info("indítás: %s (%s)", exe, program.slug)
        self._spawn(env, exe.parent, *self._wrapped("umu-run", [str(exe)]))

    def _start_wine(self, program, exe, env):
        """Tartalék: nincs Proton és nincs internet. A rendszer Wine-ja indítja a programot."""
        log.info("indítás tartalék futtatóval: %s (%s)", exe, program.slug)
        # A Gecko-telepítő kérdése ne jöjjön elő (a .NET-et a wine-mono csomag adja)
        env.insert("WINEDLLOVERRIDES", "winemenubuilder.exe=d;mshtml=d")
        args = ["msiexec", "/i", str(exe)] if exe.suffix.lower() == ".msi" else [str(exe)]
        self.setup_done.emit()
        if (program.prefix / "system.reg").exists():
            self._spawn(env, exe.parent, *self._wrapped("wine", args))
            return
        # Új mappa: előbb kijelző nélkül előkészítjük, így nem jelenik meg a Wine saját
        # "konfiguráció frissítése" ablaka; utána indul a program
        self._pending = (env, exe.parent, args)
        headless = QProcessEnvironment(env)
        headless.remove("DISPLAY")
        headless.remove("WAYLAND_DISPLAY")
        self.status.emit("status.first_setup", -1)
        self._spawn(headless, exe.parent, "wineboot", ["--init"])

    def _wrapped(self, program, args):
        """A program elé kerülnek a játékbeállítások parancsai (pl. gamescope … -- gamemoderun mangohud)."""
        if not self._wrap:
            return program, args
        log.info("játékbeállítások: %s", " ".join(self._wrap))
        return self._wrap[0], self._wrap[1:] + [program] + list(args)

    @staticmethod
    def _screen():
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return (1920, 1080)
        return (int(screen.size().width() * screen.devicePixelRatio()),
                int(screen.size().height() * screen.devicePixelRatio()))

    def _spawn(self, env, cwd, program, args):
        self._proc = QProcess(self)
        self._proc.setProcessEnvironment(env)
        self._proc.setWorkingDirectory(str(cwd))
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.start(program, args)

    def running(self):
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def elapsed(self):
        return time.monotonic() - self._started_at

    def _read(self):
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if not line:
                continue
            log.debug("%s", line)
            low = line.lower()
            for patterns, text in _STAGES:
                if any(p in low for p in patterns):
                    self._setup_seen = True
                    m = _PERCENT.search(line)
                    self.status.emit(text, int(m.group(1)) if m else -1)
                    break
            else:
                # Amint a Proton maga szólal meg, az előkészítés véget ért
                if self._setup_seen and ("proton" in low or "wine" in low or "fsync" in low):
                    self._setup_seen = False
                    self.setup_done.emit()

    def _on_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            log.error("a futtató nem indult el: %s", self._proc.program())
            self.finished.emit(127, 0.0)

    def _on_finished(self, code, _status):
        if self._pending:
            # a mappa elkészült (wineboot), most jön maga a program
            env, cwd, args = self._pending
            self._pending = None
            self._spawn(env, cwd, *self._wrapped("wine", args))
            return
        self.finished.emit(int(code), self.elapsed())
