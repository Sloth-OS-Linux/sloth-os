"""A Sloth Központ indítása: Qt alkalmazás, QML felület, vezérlők."""
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

QML_DIR = Path(__file__).resolve().parent / "qml"


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    # Natív KDE kinézet (a rendszer színsémáját követi)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    app = QApplication(sys.argv)
    app.setApplicationName("sloth-center")
    app.setApplicationDisplayName("Sloth Központ")
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.center")
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))

    # A vezérlők a gi-t (GLib) használják; a Qt eseményhurka a GLib-é, így a
    # D-Bus callbackek gond nélkül megérkeznek.
    from .updates import UpdatesController
    from .drivers import DriversController
    from .health import HealthController
    from .services import ServicesController
    from .winprograms import WinProgramsController

    engine = QQmlApplicationEngine()
    updates = UpdatesController()
    winprograms = WinProgramsController()
    services = ServicesController()
    drivers = DriversController()
    health = HealthController()
    engine.rootContext().setContextProperty("updates", updates)
    engine.rootContext().setContextProperty("winprograms", winprograms)
    engine.rootContext().setContextProperty("services", services)
    engine.rootContext().setContextProperty("drivers", drivers)
    engine.rootContext().setContextProperty("health", health)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
