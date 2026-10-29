"""Starting the .exe handler.

  sloth-exe <file>                    double-click on a Windows program (.exe, .msi), a Linux
                                      package (AppImage, .deb, .rpm) or a Mac file
  sloth-exe --launch <program> <exe>  from a Start menu entry (exe: relative to the program's environment)
  sloth-exe --run <program> [files]   starts an installed AppImage (without Qt, at once)
  sloth-exe --open-url <program> <url> a link type the program registered (e.g. a login from the browser)
  sloth-exe --shortcuts <program>     edits the Start menu entries (from Sloth Center)
  sloth-exe --maintenance             background maintenance (sloth-windows-prepare)
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
    parser.add_argument("--open-url", nargs=2, metavar=("PROGRAM", "URL"))
    parser.add_argument("--shortcuts", metavar="PROGRAM", help="edit the Start menu entries")
    parser.add_argument("--run", metavar="PROGRAM", help="start an installed AppImage")
    parser.add_argument("--queued", action="store_true",
                        help="from Sloth Welcome's install queue: the install starts at once, and \"Start\" runs the "
                             "program in a separate process, so the queue can go on with the next installer")
    parser.add_argument("--maintenance", action="store_true",
                        help="background maintenance (sloth-windows-prepare): migrating to the new location, "
                             "updating AppImages, deleting old Proton versions, sending reports")
    args, qt_args = parser.parse_known_args()
    if args.run:
        # Fast path from the Start menu: the library gives the program's location (after moving it too), no Qt needed
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
        print("Programs moved to the new location:", ", ".join(a.name for a in moved) if moved else "none")
        from sloth_common.apps import packages
        updated = packages.update_appimages()
        print("Updated AppImages:", ", ".join(updated) if updated else "none")
        removed = heal.prune_protons()
        print("Deleted old versions:", ", ".join(removed) if removed else "none")
        print("Reports sent (shared knowledge):", community.send_queue())
        return 0
    if not args.file and not args.launch and not args.shortcuts and not args.run and not args.open_url:
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
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))  # replaced by the program's own icon as soon as it is known
    # While running, the window is hidden, but we watch the program until it exits
    app.setQuitOnLastWindowClosed(False)

    from .controller import ExeController

    exe = ExeController(queued=args.queued)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("exe", exe)
    if args.run:
        exe.missing(args.run)  # the installed AppImage is missing (deleted or moved)
    elif args.launch:
        exe.launch(*args.launch)
    elif args.open_url:
        exe.open_url(*args.open_url)
    elif args.shortcuts:
        exe.manage_shortcuts(args.shortcuts)
    else:
        exe.open_file(args.file)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    # Closing the window (X) = quitting, unless the program runs in the background
    if args.queued and exe.state == "choose" and not exe.alreadyInstalled:
        # from the queue: the installer starts at once (without the "Install" button), as soon as the interface is ready
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, exe.install)
    window = engine.rootObjects()[0]
    # (exe.close: if the installer still runs, it waits for its end and does not interrupt it)
    window.closing.connect(lambda *_: exe.state != "running" and exe.close())
    return app.exec()
