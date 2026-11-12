"""Remote help (Sloth Center → Help): someone the user knows sees the screen and helps, over the internet.

RustDesk does it (com.rustdesk.RustDesk on Flathub, verified, open source; it also runs on Windows, macOS and
phones, so the helper can be on anything). It is not preinstalled (nothing is): the button opens it in Discover, and
then opens it. RustDesk shows an ID and a one-time password; on Wayland, KDE asks the user to allow the screen
sharing and the remote control at each session (xdg-desktop-portal), so nobody gets in without the user saying yes.
The card warns about the "support call" scam before anything else.
"""
import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

log = logging.getLogger("sloth-center.remote-help")

APP = "com.rustdesk.RustDesk"
APP_DIRS = (Path("/var/lib/flatpak/app") / APP, Path.home() / ".local/share/flatpak/app" / APP)


def installed():
    return any(p.is_dir() for p in APP_DIRS)


class RemoteHelpController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed = installed()
        self._waiting = False
        self._checks = 0
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._check)

    @Property(bool, notify=changed)
    def installed(self):
        return self._installed

    @Property(bool, notify=changed)
    def waiting(self):
        """Discover is open for it: the button waits until it is installed."""
        return self._waiting

    @Slot()
    def start(self):
        self._installed = installed()
        if self._installed:
            try:
                subprocess.Popen(["flatpak", "run", APP], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                log.warning("RustDesk: %s", e)
        else:
            try:
                subprocess.Popen(["plasma-discover", f"appstream://{APP}"], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                log.warning("Discover: %s", e)
                return
            self._waiting, self._checks = True, 0
            self._timer.start()
        self.changed.emit()

    def _check(self):
        self._checks += 1
        if installed():
            self._timer.stop()
            self._installed, self._waiting = True, False
            self.start()          # installed: open it at once, the user asked for help
        elif self._checks > 300:  # 10 minutes: not installed after all
            self._timer.stop()
            self._waiting = False
        self.changed.emit()
