"""A Sloth Központ indítása: Qt alkalmazás, QML felület, vezérlők."""
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

QML_DIR = Path(__file__).resolve().parent / "qml"


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    # Natív KDE kinézet (a rendszer színsémáját követi)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    # sloth-center --page <modul> : rögtön ezt az oldalt nyitja meg (pl. drivers)
    start_page = ""
    if "--page" in sys.argv[1:-1]:
        i = sys.argv.index("--page")
        start_page = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    app = QApplication(sys.argv)
    app.setApplicationName("sloth-center")
    from .i18n import Translator, catalog, tr
    app.setApplicationDisplayName(tr("Sloth Központ"))
    if catalog.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.center")
    app.setWindowIcon(QIcon.fromTheme("sloth-os"))

    # A vezérlők a gi-t (GLib) használják; a Qt eseményhurka a GLib-é, így a
    # D-Bus callbackek gond nélkül megérkeznek.
    from .updates import UpdatesController
    from .accounts import AccountsController
    from .advanced import AdvancedController
    from .containers import ContainersController
    from .devpanel import DevPanelController
    from .disks import DisksController
    from .drivers import DriversController
    from .environment import EnvironmentController
    from .gamepads import GamepadsController
    from .games import GamesController
    from .health import HealthController
    from .services import ServicesController
    from .winprograms import WinProgramsController

    engine = QQmlApplicationEngine()
    translator = Translator()
    engine.rootContext().setContextProperty("L", translator)
    engine.rootContext().setContextProperty("startPage", start_page)
    updates = UpdatesController()
    winprograms = WinProgramsController()
    services = ServicesController()
    drivers = DriversController()
    health = HealthController()
    disks = DisksController()
    advanced = AdvancedController()
    containers = ContainersController()
    environment = EnvironmentController()
    gamepads = GamepadsController()
    accounts = AccountsController()
    games = GamesController()
    devpanel = DevPanelController()
    engine.rootContext().setContextProperty("updates", updates)
    engine.rootContext().setContextProperty("winprograms", winprograms)
    engine.rootContext().setContextProperty("services", services)
    engine.rootContext().setContextProperty("drivers", drivers)
    engine.rootContext().setContextProperty("health", health)
    engine.rootContext().setContextProperty("disks", disks)
    engine.rootContext().setContextProperty("advanced", advanced)
    engine.rootContext().setContextProperty("containers", containers)
    engine.rootContext().setContextProperty("environment", environment)
    engine.rootContext().setContextProperty("gamepads", gamepads)
    engine.rootContext().setContextProperty("accounts", accounts)
    engine.rootContext().setContextProperty("games", games)
    engine.rootContext().setContextProperty("devpanel", devpanel)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
