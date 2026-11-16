"""Games → Game mode: the switch, and whether it is on right now (sloth_common/game_mode.py, the game-mode service).

The service (sloth-game-mode.service) reads the setting at every look, so turning it off ends a running game mode
within seconds, and turning it on catches a game already running.
"""
import logging
import subprocess

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from sloth_common import game_mode as gm

log = logging.getLogger("sloth-center.game-mode")


class GameModeController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = gm.load()["enabled"]
        self._playing = ""
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    enabled = Property(bool, lambda self: self._enabled, notify=changed)
    playing = Property(str, lambda self: self._playing, notify=changed)   # the game(s) now, "" if none

    @Slot()
    def refresh(self):
        state = gm.read_state()
        playing = state.get("name", "") if state else ""
        enabled = gm.load()["enabled"]
        if (playing, enabled) != (self._playing, self._enabled):
            self._playing, self._enabled = playing, enabled
            self.changed.emit()

    @Slot(bool)
    def setEnabled(self, on):
        try:
            gm.save(on)
        except OSError as e:
            log.warning("game mode: %s", e)
            return
        # the service runs in every session; started here too, in case it was stopped
        if on:
            subprocess.run(["systemctl", "--user", "start", "--no-block", "sloth-game-mode.service"],
                           capture_output=True)
        self._enabled = on
        self.changed.emit()
