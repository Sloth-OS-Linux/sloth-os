"""Starting the Sloth OS installer (only in the live system)."""
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
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    app = QApplication(sys.argv)
    app.setApplicationName("sloth-installer")
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.installer")
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))

    from .controller import InstallerController

    engine = QQmlApplicationEngine()
    installer = InstallerController()
    engine.rootContext().setContextProperty("installer", installer)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
