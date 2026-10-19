"""A .exe kezelő indítása.

  sloth-exe <fájl>                    dupla kattintás egy Windows-programra (.exe, .msi), egy Linuxos
                                      csomagra (AppImage, .deb, .rpm) vagy egy Mac-es fájlra
  sloth-exe --launch <program> <exe>  Start menü bejegyzésből (exe: a program környezetéhez képest)
  sloth-exe --run <program> [fájlok]  telepített AppImage indítása (Qt nélkül, azonnal)
  sloth-exe --shortcuts <program>     Start menü bejegyzések szerkesztése (a Sloth Központból)
  sloth-exe --maintenance             háttérkarbantartás (sloth-windows-prepare)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

QML_DIR = Path(__file__).resolve().parent / "qml"


def main():
    parser = argparse.ArgumentParser(prog="sloth-exe")
    parser.add_argument("file", nargs="?")
    parser.add_argument("--launch", nargs=2, metavar=("PROGRAM", "EXE"))
    parser.add_argument("--shortcuts", metavar="PROGRAM", help="Start menü bejegyzések szerkesztése")
    parser.add_argument("--run", metavar="PROGRAM", help="telepített AppImage indítása")
    parser.add_argument("--maintenance", action="store_true",
                        help="háttérkarbantartás (sloth-windows-prepare): átköltözés az új helyre, "
                             "AppImage-ek frissítése, régi Proton-verziók törlése, jelentések küldése")
    args, qt_args = parser.parse_known_args()
    if args.run:
        # Gyors út a Start menüből: a program helyét a könyvtár adja (áthelyezés után is), Qt nem kell
        from sloth_common.apps import library, packages

        app = library.find(args.run)
        path = packages.appimage_path(app) if app else None
        if path and path.is_file():
            files = ([args.file] if args.file else []) + [a for a in qt_args if not a.startswith("-")]
            os.chdir(Path.home())
            os.execv(str(path), [str(path)] + files)
        args.launch = None
        args.file = None
    if args.maintenance:
        from sloth_common.apps import library

        from . import community, heal
        moved = library.migrate_legacy()
        print("Új helyre költözött programok:", ", ".join(a.name for a in moved) if moved else "nincs")
        from sloth_common.apps import packages
        updated = packages.update_appimages()
        print("Frissített AppImage-ek:", ", ".join(updated) if updated else "nincs")
        removed = heal.prune_protons()
        print("Törölt régi verziók:", ", ".join(removed) if removed else "nincs")
        print("Elküldött jelentések (közös tudás):", community.send_queue())
        return 0
    if not args.file and not args.launch and not args.shortcuts and not args.run:
        parser.print_usage()
        return 2

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

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
    if args.run:
        exe.missing(args.run)  # a telepített AppImage nincs meg (törölve vagy áthelyezve)
    elif args.launch:
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
