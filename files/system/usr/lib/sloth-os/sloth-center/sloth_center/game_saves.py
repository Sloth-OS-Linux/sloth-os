"""Game saves (Games page): an hourly backup of the saves of every game, with a restore per game.

The work is done by /usr/libexec/sloth-os/game-saves with Ludusavi (Flathub), which knows where about 20 000 games
keep their saves, Proton games included. Ludusavi is installed from Discover, like Pika Backup on the File backup
page; turning the backup on writes ~/.config/sloth-os/game-saves.json and starts the user timer
(sloth-game-saves.timer). Nothing here needs a password.
"""
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from .i18n import tr

log = logging.getLogger("sloth-center.game-saves")

SCRIPT = "/usr/libexec/sloth-os/game-saves"
APP = "com.github.mtkennerly.ludusavi"
HOME = Path.home()
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
SETTINGS = CONFIG_HOME / "sloth-os/game-saves.json"
DEST = DATA_HOME / "sloth-os/game-saves"
SUMMARY = DEST / "summary.json"
APP_DIRS = (Path("/var/lib/flatpak/app") / APP, DATA_HOME / "flatpak/app" / APP)


def ludusavi_installed():
    return any(p.is_dir() for p in APP_DIRS)


def is_enabled():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8")).get("enabled") is True
    except (OSError, ValueError, AttributeError):
        return False


def set_enabled(on):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps({"enabled": bool(on)}), encoding="utf-8")
    subprocess.run(["systemctl", "--user", "enable" if on else "disable", "--now", "sloth-game-saves.timer"],
                   capture_output=True, timeout=30)


def read_summary():
    try:
        data = json.loads(SUMMARY.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def size_text(n):
    for unit, size in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= size:
            return f"{n / size:.1f} {unit}"
    return f"{n} B"


def when_text(ts):
    """"today at 14:05", "yesterday at 9:30" or the date, in the user's own format."""
    try:
        from PySide6.QtCore import QDateTime, QLocale
        dt = QDateTime.fromSecsSinceEpoch(int(ts))
        days = dt.date().daysTo(QDateTime.currentDateTime().date())
        clock = QLocale().toString(dt.time(), QLocale.FormatType.ShortFormat)
        if days == 0:
            return tr("today at {time}", time=clock)
        if days == 1:
            return tr("yesterday at {time}", time=clock)
        return QLocale().toString(dt, QLocale.FormatType.ShortFormat)
    except Exception:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def iso_to_ts(text):
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0


class GameSavesController(QObject):
    changed = Signal()
    _listed = Signal(object)
    _done = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed = ludusavi_installed()
        self._enabled = is_enabled()
        self._summary = {}
        self._backups = {}
        self._busy = ""        # "", "backup", "restore", "list"
        self._error = ""
        self._info = ""
        self._install_timer = QTimer(self)
        self._install_timer.setInterval(2000)
        self._install_timer.timeout.connect(self._check_install)
        self._checks = 0
        self._listed.connect(self._on_listed)
        self._done.connect(self._on_done)
        self.refresh()

    installed = Property(bool, lambda self: self._installed, notify=changed)
    enabled = Property(bool, lambda self: self._enabled, notify=changed)
    busy = Property(str, lambda self: self._busy, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Property(str, notify=changed)
    def lastBackup(self):
        when = self._summary.get("when")
        return tr("Last backup: {when}", when=when_text(when)) if when else ""

    @Property("QVariantList", notify=changed)
    def saves(self):
        """[{name, size, when}] of the games with a backup, newest first."""
        sizes = self._summary.get("games", {})
        out = []
        for name, info in self._backups.items():
            ts = iso_to_ts(info.get("when", ""))
            out.append({"name": name, "size": size_text(sizes[name]) if name in sizes else "",
                        "when": when_text(ts) if ts else "", "ts": ts})
        return sorted(out, key=lambda g: -g["ts"])

    @Slot()
    def refresh(self):
        self._installed = ludusavi_installed()
        self._enabled = is_enabled()
        self._summary = read_summary()
        self.changed.emit()
        if self._installed and self._enabled and not self._busy:
            self._busy = "list"
            self.changed.emit()
            threading.Thread(target=self._list, daemon=True).start()

    def _list(self):
        try:
            r = subprocess.run([SCRIPT, "list"], capture_output=True, text=True, timeout=300)
            data = json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("list: %s", e)
            data = {}
        self._listed.emit(data if isinstance(data, dict) else {})

    def _on_listed(self, data):
        self._backups = data
        if self._busy == "list":
            self._busy = ""
        self.changed.emit()

    @Slot()
    def turnOn(self):
        """Ludusavi from Discover if it is missing (the user clicks Install there), then the hourly backup."""
        self._error, self._info = "", ""
        set_enabled(True)
        self._enabled = True
        if not ludusavi_installed():
            subprocess.Popen(["plasma-discover", f"appstream://{APP}"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._checks = 0
            self._install_timer.start()
        else:
            self.backupNow()
        self.changed.emit()

    def _check_install(self):
        self._checks += 1
        if ludusavi_installed():
            self._install_timer.stop()
            self._installed = True
            self.backupNow()
        elif self._checks > 300:  # 10 minutes: the user did not install it
            self._install_timer.stop()
        self.changed.emit()

    @Slot()
    def turnOff(self):
        set_enabled(False)
        self._enabled = False
        self._info = tr("Game saves are no longer backed up. The backups made so far stay.")
        self.changed.emit()

    @Slot()
    def backupNow(self):
        if self._busy in ("backup", "restore"):
            return
        self._busy, self._error, self._info = "backup", "", ""
        self.changed.emit()

        def work():
            try:
                ok = subprocess.run([SCRIPT, "backup"], capture_output=True, text=True, timeout=3600).returncode == 0
            except (OSError, subprocess.SubprocessError) as e:
                log.warning("backup: %s", e)
                ok = False
            self._done.emit("backup", ok)
        threading.Thread(target=work, daemon=True).start()

    @Slot(str)
    def restore(self, name):
        if self._busy in ("backup", "restore") or name not in self._backups:
            return
        self._busy, self._error, self._info = "restore", "", ""
        self.changed.emit()

        def work():
            try:
                ok = subprocess.run([SCRIPT, "restore", name], capture_output=True, text=True,
                                    timeout=1800).returncode == 0
            except (OSError, subprocess.SubprocessError) as e:
                log.warning("restore %s: %s", name, e)
                ok = False
            self._done.emit("restore:" + name, ok)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, kind, ok):
        self._busy = ""
        if kind == "backup":
            if ok:
                self._info = tr("Your game saves are backed up.")
            else:
                self._error = tr("Couldn't back up the game saves. Check the internet connection the first time, "
                                 "then try again.")
        else:
            name = kind.split(":", 1)[1]
            if ok:
                self._info = tr("{game}: the save from the backup is back. Start the game to continue from there.",
                                game=name)
            else:
                self._error = tr("{game}: couldn't put the save back. Close the game if it is running, then try "
                                 "again.", game=name)
        self.refresh()

    @Slot()
    def openFolder(self):
        DEST.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(DEST)))
