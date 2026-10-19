"""A Sloth Üdvözlő indítása."""
import argparse
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--first-run", action="store_true",
                        help="automatikus indítás: csak akkor nyílik meg, ha még nem futott")
    parser.add_argument("--windows-import", action="store_true",
                        help="csak a fájlok áthozása a Windowsból (a Sloth Központ Lemezek oldaláról)")
    args, qt_args = parser.parse_known_args()

    from .welcome import DONE_MARKER
    if args.first_run and DONE_MARKER.exists():
        return 0

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("sloth-welcome")
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.welcome")
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))

    from .welcome import WelcomeController, apply_language
    apply_language()

    engine = QQmlApplicationEngine()
    welcome = WelcomeController(windows_only=args.windows_import)
    # ha az ablakot bezárják, a Windows-partíció se maradjon csatolva
    app.aboutToQuit.connect(welcome.release_windows)
    engine.rootContext().setContextProperty("welcome", welcome)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
