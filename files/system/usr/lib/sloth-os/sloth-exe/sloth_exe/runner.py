"""Windows-program indítása a háttérben (umu-launcher + Proton, tartalékként a rendszer Wine-ja).

A felhasználó a technikai részleteket nem látja: a kimenetből csak emberi
állapotszöveg lesz ("Első indítás előkészítése…"), a többi a naplóba megy
(~/.cache/sloth-os/apps/<program>/naplo/<exe>.log), és abból dolgozik az önjavítás (diagnose.py, heal.py).
Hogy melyik futtató indul, azt a backend.py dönti el.
"""
import collections
import logging
import re
import subprocess
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal
from PySide6.QtGui import QGuiApplication

from sloth_common import gamesettings
from sloth_common.apps.library import slugify

from . import backend, quirks, stagedlinks

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
LOG_LINES = 5000             # ennyi utolsó sort tartunk meg a diagnózishoz
LOG_MAX_BYTES = 2 * 1024**2  # a naplófájl legfeljebb ekkora


PREPARE_UNIT = "sloth-windows-prepare.service"


def _take_over_prepare():
    """Ha a háttérben épp a futtató letöltése megy (sloth-windows-prepare), leállítjuk: a felhasználó vár, ezért a
    letöltést most az előtérben, normál prioritással és látható haladással végezzük. Különben az umu csendben
    megvárná a háttérben, a legalacsonyabb prioritással futó letöltést (friss telepítés után akár percekig)."""
    try:
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", PREPARE_UNIT], timeout=5).returncode:
            return
        log.info("a háttérben futó előkészítés leállítása, az előtérben folytatjuk")
        subprocess.run(["systemctl", "--user", "stop", PREPARE_UNIT], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", PREPARE_UNIT, e)


class Runner(QObject):
    status = Signal(str, int)   # állapot fordítási kulcsa, százalék (-1 = ismeretlen)
    setup_done = Signal()       # az előkészítés kész, a program elindult
    finished = Signal(int, float)  # kilépési kód, futási idő (mp)
    verb_done = Signal(str, int)   # egy hiányzó összetevő telepítése lefutott (név, kilépési kód)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._links = None      # stagedlinks.Watcher, amíg a program fut (EA app)
        self._prefix = None     # a futó program Windows-környezete (a kihagyott linkek pótlásához)
        self._started_at = 0.0
        self._setup_seen = False
        self._steps = []      # a program előtt futó lépések: (env, cwd, parancs, args, összetevő neve)
        self._wrap = []       # játékbeállítások (FPS-kijelző, teljesítmény mód, felskálázás) parancsai
        self._lines = collections.deque(maxlen=LOG_LINES)
        self._log_file = None
        self._log_bytes = 0
        self.uses_wine = False

    def lines(self):
        return list(self._lines)

    def start(self, program, exe, attempt=None, gameid=None, join=False):
        """program: library.App, exe: a futtatandó fájl a gazdagépen.

        attempt: heal.Attempt (melyik Proton, milyen beállítással, milyen javításokkal), gameid: umu GAMEID.
        join: a program környezetében már fut valami (pl. az indító, amiből ez a játék is indulhatna):
        az új program ahhoz csatlakozik, és nem várja meg, amíg az előző leáll.
        """
        program.prefix.mkdir(parents=True, exist_ok=True)
        self._prefix = program.prefix
        env = QProcessEnvironment.systemEnvironment()
        env.insert("WINEPREFIX", str(program.prefix))
        env.insert("GAMEID", gameid or program.meta.get("gameid") or "umu-default")
        env.insert("STORE", "none")
        # Indítás előtt megvárjuk, amíg az előző munkamenet (wineserver) leáll. A gyerekfolyamatokat
        # ez nem várja meg: a futtató az elindított folyamattal együtt leáll, és vele zárul be, amit
        # az elindított. A rövid életű indítók helyett ezért a klienst indítjuk (quirks.launch_target).
        # Ha a környezetben már fut valami, ahhoz csatlakozunk (különben az indítás addig várna, amíg az leáll).
        env.insert("PROTON_VERB", "runinprefix" if join else "waitforexitandrun")
        # A hibasorok kellenek a diagnózishoz (a felhasználó nem látja őket); a "fixme" zaj nem. Kivétel a "file"
        # csatorna: a Wine 10 abban jelzi a kihagyott linkkéréseket, és azokat utólag mi hozzuk létre (stagedlinks)
        env.insert("WINEDEBUG", "fixme-all,fixme+file")
        env.insert("DXVK_LOG_LEVEL", "warn")
        env.insert("VKD3D_DEBUG", "warn")
        # A Wine ne hozzon létre saját menübejegyzéseket: azokat mi kezeljük
        env.insert("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        env.remove("UMU_ZENITY")
        # Játékonkénti beállítások a Sloth Központból (Játékok oldal)
        self._wrap = gamesettings.wrapper(program.meta.get("game"), self._screen())
        # Ismert programok (pl. Battle.net, Ubisoft Connect, Epic, GOG Galaxy) beállításai
        known = quirks.apply(program, exe, env)
        args = list(known["args"])
        # EA app: a Wine 10 nem hoz létre linket, ezért a verziócserénél mi tesszük a helyére (stagedlinks)
        self._stop_links()
        if stagedlinks.applies(program.prefix, exe):
            stagedlinks.fix(program.prefix)
            self._links = stagedlinks.Watcher(program.prefix)
            self._links.start()
        if attempt:
            for key, value in attempt.env().items():
                env.insert(key, value)
            args = attempt.args() + [a for a in args if a not in attempt.args()]

        self._open_log(program, exe)
        self._started_at = time.monotonic()
        self._steps = []
        if backend.use_wine():
            self._start_wine(program, exe, env, args)
            return
        self.uses_wine = False
        if not join:
            _take_over_prepare()
        if not backend.proton_ready() and backend.bundled():
            # A gyári Proton és futtatókörnyezet bemásolása (pár másodperc, letöltés nélkül)
            self.status.emit("status.first_setup", -1)
            self._steps.append((env, exe.parent, backend.SEED, [], ""))
        # Hiányzó összetevők telepítése a program előtt (winetricks az umu-n keresztül, kérdés nélkül)
        done = set(program.meta.get("verbs", []))
        # futó környezetbe összetevőt nem telepítünk (a következő önálló indításkor települ)
        verbs = [] if join else (attempt.verbs() if attempt else []) + known["verbs"]
        for verb in dict.fromkeys(verbs):
            if verb not in done:
                self._steps.append((env, exe.parent, "umu-run", ["winetricks", "-q", verb], verb))
        # Az .msi telepítőket a Proton magától az msiexec-kel nyitja meg
        log.info("indítás: %s (%s, %s)", exe, program.id, attempt.key if attempt else "alap")
        self._steps.append((env, exe.parent, *self._wrapped("umu-run", [str(exe)] + args), None))
        self._next_step()

    def _start_wine(self, program, exe, env, args):
        """Tartalék: nincs Proton és nincs internet. A rendszer Wine-ja indítja a programot."""
        log.info("indítás tartalék futtatóval: %s (%s)", exe, program.id)
        self.uses_wine = True
        # A Gecko-telepítő kérdése ne jöjjön elő (a .NET-et a wine-mono csomag adja)
        env.insert("WINEDLLOVERRIDES", env.value("WINEDLLOVERRIDES") + ";mshtml=d")
        cmd = (["msiexec", "/i", str(exe)] if exe.suffix.lower() == ".msi" else [str(exe)]) + args
        self.setup_done.emit()
        if not (program.prefix / "system.reg").exists():
            # Új mappa: előbb kijelző nélkül előkészítjük, így nem jelenik meg a Wine saját
            # "konfiguráció frissítése" ablaka; utána indul a program
            headless = QProcessEnvironment(env)
            headless.remove("DISPLAY")
            headless.remove("WAYLAND_DISPLAY")
            self.status.emit("status.first_setup", -1)
            self._steps.append((headless, exe.parent, "wineboot", ["--init"], ""))
        self._steps.append((env, exe.parent, *self._wrapped("wine", cmd), None))
        self._next_step()

    def _next_step(self):
        env, cwd, program, args, verb = self._steps[0]
        if len(self._steps) == 1:
            # maga a program: innen mérjük a futási időt (az előkészítés nem számít bele)
            self._started_at = time.monotonic()
        if verb:
            self.status.emit("status.repairing", -1)
            log.info("összetevő telepítése: %s", verb)
        self._spawn(env, cwd, program, args)

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

    # --- Napló -----------------------------------------------------------------------------------

    def _open_log(self, program, exe):
        self._lines.clear()
        self._close_log()
        try:
            path = program.log_dir / f"{slugify(exe.stem)}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(path, "w", encoding="utf-8")
            self._log_bytes = 0
        except OSError as e:
            log.warning("napló: %s", e)

    def _write_log(self, line):
        self._lines.append(line)
        if self._log_file and self._log_bytes < LOG_MAX_BYTES:
            self._log_file.write(line + "\n")
            self._log_bytes += len(line) + 1

    def _close_log(self):
        if self._log_file:
            self._log_file.close()
            self._log_file = None

    def _read(self):
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
            if not line:
                continue
            self._write_log(line)
            if "CreateSymbolicLinkW" in line and self._prefix:
                stagedlinks.from_log_line(self._prefix, line)
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
                    self._started_at = time.monotonic()  # a letöltés ideje nem számít a futásba
                    self.setup_done.emit()

    def _stop_links(self):
        if self._links:
            self._links.stop()
            self._links = None

    def _on_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            log.error("a futtató nem indult el: %s", self._proc.program())
            self._steps = []
            self._close_log()
            self._stop_links()
            self.finished.emit(127, 0.0)

    def _on_finished(self, code, _status):
        _env, _cwd, _program, _args, verb = self._steps.pop(0) if self._steps else (None,) * 5
        if self._steps:
            # egy előkészítő lépés (összetevő, wineboot) végzett, jön a következő
            if verb:
                self.verb_done.emit(verb, int(code))
            self._next_step()
            return
        self._close_log()
        self._stop_links()
        self.finished.emit(int(code), self.elapsed())
