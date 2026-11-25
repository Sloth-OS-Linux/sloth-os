"""The Windows programs on the Updates page: every kind of update in one place, without a Discover plugin.

The programs themselves (Battle.net, EA app, a game's launcher) update themselves when they start, as on Windows.
What Sloth OS updates for them is the Windows runtime they run on: sloth-windows-prepare (a user timer, a few
minutes after sign-in, then every 6 hours) downloads a newer one in the background. This card says when that
was last checked, lets it run now, and names a program the .exe handler keeps on an earlier runtime because it
did not start with the newest one (sloth-exe/heal.py: it tries the newest again when an even newer one comes).
The word Proton is not shown: "the Windows runtime".
"""
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from sloth_common.apps import library

from .i18n import tr

log = logging.getLogger("sloth-center.winupdates")

UNIT = "sloth-windows-prepare.service"
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
# where the .exe handler keeps the runtimes (sloth-exe/heal.py COMPAT_DIRS)
COMPAT_DIRS = [DATA_HOME / "Steam/compatibilitytools.d", DATA_HOME / "umu/compatibilitytools"]
LINE = "UMU-Proton"


def _version_key(name):
    return [int(n) for n in re.findall(r"\d+", name)]


def newest_runtime(dirs=None):
    """The newest installed runtime's name (heal.newest(UMU_LINE)), or ""."""
    names = {d.name for base in (dirs or COMPAT_DIRS) if base.is_dir() for d in base.iterdir()
             if d.name.startswith(LINE) and (d / "proton").is_file()}
    return max(names, key=_version_key) if names else ""


def held_back(apps, newest):
    """The programs kept on an earlier runtime: the newest one was tried and failed, an older one works.
    -> [name]."""
    out = []
    if not newest:
        return out
    for app in apps:
        for rec in (app.meta.get("launch") or {}).values():
            good = (rec.get("good") or {}).get("proton") or ""
            failed = rec.get("failed") or []
            if good.startswith(LINE) and good != newest and any(f.startswith(newest + "|") for f in failed):
                out.append(app.name)
                break
    return out


def _unit_state():
    """(active: the check runs now, the last finish as a Unix time or 0)."""
    try:
        r = subprocess.run(["systemctl", "--user", "show", UNIT, "-p", "ActiveState",
                            "-p", "ExecMainExitTimestampMonotonic", "-p", "ExecMainExitTimestamp",
                            "--timestamp=unix"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False, 0
    props = dict(line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)
    stamp = props.get("ExecMainExitTimestamp", "").lstrip("@")
    return props.get("ActiveState") in ("activating", "active"), int(stamp) if stamp.isdigit() else 0


class WinUpdatesController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._programs, self._held, self._running, self._last = [], [], False, 0
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._poll)
        self.refresh()

    @Slot()
    def refresh(self):
        apps = [a for a in library.all_apps() if a.kind == "windows" and a.id != library.SHARED_ID]
        self._programs = sorted(a.name for a in apps)
        self._held = held_back(apps, newest_runtime())
        self._running, self._last = _unit_state()
        if self._running and not self._timer.isActive():
            self._timer.start()
        self.changed.emit()

    def _poll(self):
        running, last = _unit_state()
        if not running:
            self._timer.stop()
        if (running, last) != (self._running, self._last):
            self.refresh()

    programs = Property("QVariantList", lambda self: list(self._programs), notify=changed)
    heldBack = Property("QVariantList", lambda self: list(self._held), notify=changed)
    running = Property(bool, lambda self: self._running, notify=changed)

    @Property(str, notify=changed)
    def runtimeText(self):
        if self._running:
            return tr("Checking for a newer Windows runtime now…")
        if not self._last:
            return tr("The Windows runtime is checked a few minutes after you sign in, then every 6 hours.")
        from PySide6.QtCore import QDateTime, QLocale
        when = QLocale().toString(QDateTime.fromSecsSinceEpoch(self._last), QLocale.FormatType.ShortFormat)
        return tr("The Windows runtime is checked by itself every 6 hours. Last checked: {when}.", when=when)

    @Slot()
    def checkNow(self):
        try:
            subprocess.run(["systemctl", "--user", "start", "--no-block", UNIT], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("%s: %s", UNIT, e)
        self._running = True
        self._timer.start()
        self.changed.emit()
        QTimer.singleShot(1500, self._poll)
