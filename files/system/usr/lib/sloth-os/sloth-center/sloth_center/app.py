"""Starting Sloth Center: the Qt application, the QML interface, the controllers."""
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
    # Native KDE look (it follows the system's color scheme)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")

    # sloth-center --page <module> : opens this page right away (e.g. drivers)
    start_page = ""
    if "--page" in sys.argv[1:-1]:
        i = sys.argv.index("--page")
        start_page = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    app = QApplication(sys.argv)
    app.setApplicationName("sloth-center")
    app.setOrganizationName("Sloth OS")
    from .i18n import Translator, catalog, tr
    app.setApplicationDisplayName(tr("Sloth Center"))
    if catalog.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.center")
    app.setWindowIcon(QIcon.fromTheme("sloth-center"))

    # The controllers use gi (GLib); Qt's event loop is GLib's, so the
    # D-Bus callbacks arrive without problems.
    from sloth_common import appearance as shared_appearance
    from .updates import UpdatesController
    from .appearance import AppearanceController
    from .accounts import AccountsController
    from .advanced import AdvancedController
    from .backup import BackupController
    from .cloud import CloudController
    from .containers import ContainersController
    from .devpanel import DevPanelController
    from .disks import DisksController
    from .drivers import DriversController
    from .environment import EnvironmentController
    from .gamepads import GamepadsController
    from .games import GamesController
    from .guide import GuideController
    from .feedback import FeedbackController
    from .health import HealthController
    from .reset import ResetController
    from .services import ServicesController
    from .startup import StartupController
    from .wifi import WifiController
    from .privacy import PrivacyController
    from .sound import SoundController
    from .display import DisplayController
    from .bluetooth import BluetoothController
    from .profiles import ProfilesController
    from .settings_backup import SettingsBackupController
    from .winprograms import WinProgramsController

    engine = QQmlApplicationEngine()
    engine.addImportPath(shared_appearance.QML_IMPORT_PATH)  # import SlothCommon (the layout drawings)
    translator = Translator()
    engine.rootContext().setContextProperty("L", translator)
    engine.rootContext().setContextProperty("startPage", start_page)
    updates = UpdatesController()
    winprograms = WinProgramsController()
    services = ServicesController()
    drivers = DriversController()
    health = HealthController()
    feedback = FeedbackController()
    disks = DisksController()
    backup = BackupController()
    advanced = AdvancedController()
    reset = ResetController()
    containers = ContainersController()
    environment = EnvironmentController()
    gamepads = GamepadsController()
    accounts = AccountsController()
    cloud = CloudController()
    games = GamesController()
    devpanel = DevPanelController()
    guide = GuideController()
    appearance = AppearanceController()
    startup = StartupController()
    wifi = WifiController()
    privacy = PrivacyController()
    sound = SoundController()
    display = DisplayController()
    bluetooth = BluetoothController()
    profiles = ProfilesController(display)
    settings_backup = SettingsBackupController()
    engine.rootContext().setContextProperty("updates", updates)
    engine.rootContext().setContextProperty("winprograms", winprograms)
    engine.rootContext().setContextProperty("services", services)
    engine.rootContext().setContextProperty("drivers", drivers)
    engine.rootContext().setContextProperty("health", health)
    engine.rootContext().setContextProperty("feedback", feedback)
    engine.rootContext().setContextProperty("disks", disks)
    engine.rootContext().setContextProperty("backup", backup)
    engine.rootContext().setContextProperty("advanced", advanced)
    engine.rootContext().setContextProperty("reset", reset)
    engine.rootContext().setContextProperty("containers", containers)
    engine.rootContext().setContextProperty("environment", environment)
    engine.rootContext().setContextProperty("gamepads", gamepads)
    engine.rootContext().setContextProperty("accounts", accounts)
    engine.rootContext().setContextProperty("cloud", cloud)
    engine.rootContext().setContextProperty("games", games)
    engine.rootContext().setContextProperty("devpanel", devpanel)
    engine.rootContext().setContextProperty("guide", guide)
    engine.rootContext().setContextProperty("appearance", appearance)
    engine.rootContext().setContextProperty("startup", startup)
    engine.rootContext().setContextProperty("wifi", wifi)
    engine.rootContext().setContextProperty("privacy", privacy)
    engine.rootContext().setContextProperty("sound", sound)
    engine.rootContext().setContextProperty("displays", display)
    engine.rootContext().setContextProperty("bluetooth", bluetooth)
    engine.rootContext().setContextProperty("profiles", profiles)
    engine.rootContext().setContextProperty("settingsBackup", settings_backup)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
