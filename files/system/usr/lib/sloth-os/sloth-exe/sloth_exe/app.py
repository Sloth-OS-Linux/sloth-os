"""A .exe kezelő indítása.

  sloth-exe <fájl.exe|fájl.msi>      dupla kattintás egy Windows-programra
  sloth-exe --launch <program> <exe>  Start menü bejegyzésből
"""
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
    parser = argparse.ArgumentParser(prog="sloth-exe")
    parser.add_argument("file", nargs="?")
    parser.add_argument("--launch", nargs=2, metavar=("PROGRAM", "EXE"))
    parser.add_argument("--shortcuts", metavar="PROGRAM", help="Start menü bejegyzések szerkesztése")
    args, qt_args = parser.parse_known_args()
    if not args.file and not args.launch and not args.shortcuts:
        parser.print_usage()
        return 2

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("sloth-exe")
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.exe")
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))  # amint ismert, a program saját ikonja váltja
    # Futás közben az ablak el van rejtve, de a programot figyeljük, amíg kilép
    app.setQuitOnLastWindowClosed(False)

    from .controller import ExeController

    exe = ExeController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("exe", exe)
    if args.launch:
        exe.launch(*args.launch)
    elif args.shortcuts:
        exe.manage_shortcuts(args.shortcuts)
    else:
        exe.open_file(args.file)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    # Az ablak bezárása (X) = kilépés, kivéve ha a program fut a háttérben
    window = engine.rootObjects()[0]
    window.closing.connect(lambda *_: exe.state != "running" and app.quit())
    return app.exec()
