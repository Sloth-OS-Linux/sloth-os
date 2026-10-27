"""Starting Sloth Welcome."""
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
                        help="automatic start: only opens if it has not run yet")
    parser.add_argument("--windows-import", action="store_true",
                        help="only bringing files over from Windows (from Sloth Center's Disks page)")
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

    from sloth_common import appearance
    from .welcome import WelcomeController, apply_language
    apply_language()

    engine = QQmlApplicationEngine()
    engine.addImportPath(appearance.QML_IMPORT_PATH)  # import SlothCommon (the layout drawings)
    welcome = WelcomeController(windows_only=args.windows_import)
    # if the window is closed, the Windows partition must not stay mounted either
    app.aboutToQuit.connect(welcome.release_windows)
    engine.rootContext().setContextProperty("welcome", welcome)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
