"""Windows-program indítása a háttérben (umu-launcher + Proton).

A felhasználó a technikai részleteket nem látja: a kimenetből csak emberi
állapotszöveg lesz ("Első indítás előkészítése…"), a többi a naplóba megy.
"""
import logging
import re
import time

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

log = logging.getLogger("sloth-exe.runner")

# umu kimenet -> emberi szöveg (az első egyező nyer, kisbetűs minták)
_STAGES = [
    (("setting up unified launcher",), "Első indítás előkészítése…"),
    (("downloading",), "Szükséges összetevők letöltése… (csak az első alkalommal)"),
    (("extracting",), "Összetevők kicsomagolása…"),
    (("verifying integrity", "sha256 is ok", "sha512 is ok", "mtree is ok"), "Ellenőrzés…"),
    (("updating",), "Összetevők frissítése…"),
    (("restoring runtime",), "Összetevők javítása…"),
]
_PERCENT = re.compile(r"(\d{1,3})(?:\.\d+)?\s?%")


class Runner(QObject):
    status = Signal(str, int)   # szöveg, százalék (-1 = ismeretlen)
    setup_done = Signal()       # az előkészítés kész, a program elindult
    finished = Signal(int, float)  # kilépési kód, futási idő (mp)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._started_at = 0.0
        self._setup_seen = False

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

        self._proc = QProcess(self)
        self._proc.setProcessEnvironment(env)
        self._proc.setWorkingDirectory(str(exe.parent))
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._on_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._started_at = time.monotonic()
        # Az .msi telepítőket a Wine magától az msiexec-kel nyitja meg
        log.info("indítás: %s (%s)", exe, program.slug)
        self._proc.start("umu-run", [str(exe)])

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
            log.error("az umu-run nem indult el")
            self.finished.emit(127, 0.0)

    def _on_finished(self, code, _status):
        self.finished.emit(int(code), self.elapsed())
