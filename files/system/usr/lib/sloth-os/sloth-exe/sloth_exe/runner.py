"""Starts a Windows program in the background (umu-launcher + Proton, with the system Wine as the fallback).

The user does not see the technical details: the output only becomes a human
status text ("Preparing the first start…"), the rest goes to the log
(~/.cache/sloth-os/apps/<program>/naplo/<exe>.log), and self-healing works from that (diagnose.py, heal.py).
backend.py decides which runner starts.
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

# umu output -> status (translation key; the first match wins, lowercase patterns)
_STAGES = [
    (("setting up unified launcher",), "status.first_setup"),
    (("downloading",), "status.downloading"),
    (("extracting",), "status.extracting"),
    (("verifying integrity", "sha256 is ok", "sha512 is ok", "mtree is ok"), "status.verifying"),
    (("updating",), "status.updating"),
    (("restoring runtime",), "status.repairing"),
]
_PERCENT = re.compile(r"(\d{1,3})(?:\.\d+)?\s?%")
LOG_LINES = 5000             # this many last lines are kept for the diagnosis
LOG_MAX_BYTES = 2 * 1024**2  # the log file is at most this big


PREPARE_UNIT = "sloth-windows-prepare.service"


def _take_over_prepare():
    """If the runner is being downloaded in the background (sloth-windows-prepare), we stop it: the user is waiting, so
    the download now happens in the foreground, with normal priority and visible progress. Otherwise umu would quietly
    wait for the background download running at the lowest priority (after a fresh install even for minutes)."""
    try:
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", PREPARE_UNIT], timeout=5).returncode:
            return
        log.info("stopping the background preparation, continuing in the foreground")
        subprocess.run(["systemctl", "--user", "stop", PREPARE_UNIT], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", PREPARE_UNIT, e)


class Runner(QObject):
    status = Signal(str, int)   # the status' translation key, percentage (-1 = unknown)
    setup_done = Signal()       # preparation done, the program started
    finished = Signal(int, float)  # exit code, run time (s)
    verb_done = Signal(str, int)   # installing a missing component finished (name, exit code)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._links = None      # stagedlinks.Watcher while the program runs (EA app)
        self._prefix = None     # the running program's Windows environment (for adding the skipped links)
        self._started_at = 0.0
        self._setup_seen = False
        self._steps = []      # the steps run before the program: (env, cwd, command, args, component name)
        self._wrap = []       # commands of the game settings (FPS display, performance mode, upscaling)
        self._lines = collections.deque(maxlen=LOG_LINES)
        self._log_file = None
        self._log_bytes = 0
        self.uses_wine = False

    def lines(self):
        return list(self._lines)

    def start(self, program, exe, attempt=None, gameid=None, join=False):
        """program: library.App, exe: the file to run on the host.

        attempt: heal.Attempt (which Proton, with which setting and fixes), gameid: umu GAMEID.
        join: something already runs in the program's environment (e.g. the launcher this game could also start from):
        the new program joins it and does not wait until the previous one stops.
        """
        program.prefix.mkdir(parents=True, exist_ok=True)
        self._prefix = program.prefix
        env = QProcessEnvironment.systemEnvironment()
        env.insert("WINEPREFIX", str(program.prefix))
        env.insert("GAMEID", gameid or program.meta.get("gameid") or "umu-default")
        env.insert("STORE", "none")
        # Before starting we wait until the previous session (wineserver) stops. This does not wait
        # for child processes: the runner stops together with the started process, and closes what
        # that started. So instead of short-lived launchers we start the client (quirks.launch_target).
        # If something already runs in the environment, we join it (otherwise the start would wait until it stops).
        env.insert("PROTON_VERB", "runinprefix" if join else "waitforexitandrun")
        # The error lines are needed for the diagnosis (the user does not see them); the "fixme" noise is not. Except the "file"
        # channel: Wine 10 reports the skipped link requests in it, and we create those afterwards (stagedlinks)
        env.insert("WINEDEBUG", "fixme-all,fixme+file")
        env.insert("DXVK_LOG_LEVEL", "warn")
        env.insert("VKD3D_DEBUG", "warn")
        # Wine must not create its own menu entries: we handle those
        env.insert("WINEDLLOVERRIDES", "winemenubuilder.exe=d")
        env.remove("UMU_ZENITY")
        # Per-game settings from Sloth Center (Games page)
        self._wrap = gamesettings.wrapper(program.meta.get("game"), self._screen())
        # Settings of known programs (e.g. Battle.net, Ubisoft Connect, Epic, GOG Galaxy)
        known = quirks.apply(program, exe, env)
        args = list(known["args"])
        # EA app: Wine 10 does not create a link, so on a version change we put it in place (stagedlinks)
        self._stop_links()
        if stagedlinks.applies(program.prefix, exe):
            stagedlinks.fix(program.prefix)
            self._links = stagedlinks.Watcher(program.prefix)
            self._links.start()
        if attempt:
            for key, value in attempt.env().items():
                env.insert(key, value)
            args = attempt.args() + [a for a in args if a not in attempt.args()]
        # Do not download a newer Proton / runtime while the user waits (it updates in the background)
        proton, runtime = backend.local_runtime()
        if proton and not env.contains("PROTONPATH"):
            env.insert("PROTONPATH", proton)
        if runtime:
            env.insert("UMU_RUNTIME_UPDATE", "0")

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
            # Copying in the bundled Proton and runtime (a few seconds, no download)
            self.status.emit("status.first_setup", -1)
            self._steps.append((env, exe.parent, backend.SEED, [], ""))
        # Installing missing components before the program (winetricks through umu, without questions)
        done = set(program.meta.get("verbs", []))
        # no component is installed into a running environment (it gets installed on the next standalone start)
        verbs = [] if join else (attempt.verbs() if attempt else []) + known["verbs"]
        for verb in dict.fromkeys(verbs):
            if verb not in done:
                self._steps.append((env, exe.parent, "umu-run", ["winetricks", "-q", verb], verb))
        # Proton opens .msi installers with msiexec by itself
        log.info("starting: %s (%s, %s)", exe, program.id, attempt.key if attempt else "default")
        self._steps.append((env, exe.parent, *self._wrapped("umu-run", [str(exe)] + args), None))
        self._next_step()

    def _start_wine(self, program, exe, env, args):
        """Fallback: no Proton and no internet. The system Wine starts the program."""
        log.info("starting with the fallback runner: %s (%s)", exe, program.id)
        self.uses_wine = True
        # The Gecko installer's question must not come up (.NET comes from the wine-mono package)
        env.insert("WINEDLLOVERRIDES", env.value("WINEDLLOVERRIDES") + ";mshtml=d")
        cmd = (["msiexec", "/i", str(exe)] if exe.suffix.lower() == ".msi" else [str(exe)]) + args
        self.setup_done.emit()
        if not (program.prefix / "system.reg").exists():
            # A new folder: first we prepare it without a display, so Wine's own
            # "updating the configuration" window does not appear; then the program starts
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
            # the program itself: the run time is measured from here (preparation does not count)
            self._started_at = time.monotonic()
        if verb:
            self.status.emit("status.repairing", -1)
            log.info("installing component: %s", verb)
        self._spawn(env, cwd, program, args)

    def _wrapped(self, program, args):
        """The game settings' commands go in front of the program (e.g. gamescope … -- gamemoderun mangohud)."""
        if not self._wrap:
            return program, args
        log.info("game settings: %s", " ".join(self._wrap))
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

    def main_running(self):
        """The program itself is running now (the preparation steps, e.g. installing components, have ended)."""
        return self.running() and len(self._steps) == 1

    def elapsed(self):
        return time.monotonic() - self._started_at

    # --- Log -----------------------------------------------------------------------------------

    def _open_log(self, program, exe):
        self._lines.clear()
        self._close_log()
        try:
            path = program.log_dir / f"{slugify(exe.stem)}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(path, "w", encoding="utf-8")
            self._log_bytes = 0
        except OSError as e:
            log.warning("log: %s", e)

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
                # As soon as Proton itself speaks, the preparation is over
                if self._setup_seen and ("proton" in low or "wine" in low or "fsync" in low):
                    self._setup_seen = False
                    self._started_at = time.monotonic()  # the download time does not count towards the run
                    self.setup_done.emit()

    def _stop_links(self):
        if self._links:
            self._links.stop()
            self._links = None

    def _on_error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            log.error("the runner did not start: %s", self._proc.program())
            self._steps = []
            self._close_log()
            self._stop_links()
            self.finished.emit(127, 0.0)

    def _on_finished(self, code, _status):
        _env, _cwd, _program, _args, verb = self._steps.pop(0) if self._steps else (None,) * 5
        if self._steps:
            # a preparation step (component, wineboot) finished, the next one comes
            if verb:
                self.verb_done.emit(verb, int(code))
            self._next_step()
            return
        self._close_log()
        self._stop_links()
        self.finished.emit(int(code), self.elapsed())
