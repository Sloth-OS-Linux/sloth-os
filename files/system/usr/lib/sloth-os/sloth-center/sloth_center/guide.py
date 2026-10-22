"""Remember whether the optional Sloth Center first-run guide was dismissed."""
from PySide6.QtCore import QObject, Property, QSettings, Signal, Slot


class GuideController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = QSettings()

    @Property(bool, notify=changed)
    def seen(self):
        return self._settings.value("firstRunGuideSeen", False, type=bool)

    @Slot()
    def markSeen(self):
        self._settings.setValue("firstRunGuideSeen", True)
        self._settings.sync()
        self.changed.emit()
