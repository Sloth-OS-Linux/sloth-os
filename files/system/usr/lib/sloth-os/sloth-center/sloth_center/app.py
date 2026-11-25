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
    # sloth-center --kcm <page> [--kcm-args "<arguments>"] : a KDE settings page (from `systemsettings <page>`)
    # sloth-center --page games --game steam:<appid> : a game's settings at once (the "closed right after it
    # started" notification, game_doctor.py)
    start_kcm = start_kcm_args = start_game = ""
    for opt in ("--kcm", "--kcm-args", "--game"):
        if opt in sys.argv[1:-1]:
            i = sys.argv.index(opt)
            value = sys.argv[i + 1]
            if opt == "--kcm":
                start_kcm = value
            elif opt == "--kcm-args":
                start_kcm_args = value
            else:
                start_game = value
            del sys.argv[i:i + 2]
    # One window only: if Sloth Center is already open, it shows the page and comes forward, and this one quits
    from .single_instance import SingleInstance, claim_or_forward
    if claim_or_forward(start_page, start_kcm, start_kcm_args, start_game):
        return 0
    app = QApplication(sys.argv)
    instance = SingleInstance()
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
    from .winupdates import WinUpdatesController
    from .restore_ui import RestorePointsController
    from .appearance import AppearanceController
    from .accounts import AccountsController
    from .family import FamilyController
    from .guest import GuestController
    from .accessibility import AccessibilityController
    from .power import PowerController
    from .game_saves import GameSavesController
    from .game_mode_ctl import GameModeController
    from .advanced import AdvancedController
    from .backup import BackupController
    from .cloud import CloudController
    from .containers import ContainersController
    from .devpanel import DevPanelController
    from .disks import DisksController
    from .netfolders import NetFoldersController
    from .sharing import SharingController
    from .netlimit import NetLimitController
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
    from .firmware import FirmwareController
    from .remote_help import RemoteHelpController
    from .printers import PrintersController
    from .kde_settings import KdeSettingsController
    from .search import SearchIndex
    from .network import NetworkController
    from .installed_apps import AppsController

    engine = QQmlApplicationEngine()
    engine.addImportPath(shared_appearance.QML_IMPORT_PATH)  # import SlothCommon (the layout drawings)
    translator = Translator()
    engine.rootContext().setContextProperty("L", translator)
    search_index = SearchIndex()
    engine.rootContext().setContextProperty("searchIndex", search_index)
    engine.rootContext().setContextProperty("startPage", start_page)
    engine.rootContext().setContextProperty("startKcm", start_kcm)
    engine.rootContext().setContextProperty("startKcmArgs", start_kcm_args)
    engine.rootContext().setContextProperty("startGame", start_game)
    engine.rootContext().setContextProperty("instance", instance)
    updates = UpdatesController()
    win_updates = WinUpdatesController()
    firmware = FirmwareController()
    remote_help = RemoteHelpController()
    printers = PrintersController()
    kde = KdeSettingsController()
    winprograms = WinProgramsController()
    services = ServicesController()
    drivers = DriversController()
    health = HealthController()
    feedback = FeedbackController()
    disks = DisksController()
    netfolders = NetFoldersController()
    sharing = SharingController()
    netlimit = NetLimitController()
    backup = BackupController()
    advanced = AdvancedController()
    reset = ResetController()
    containers = ContainersController()
    environment = EnvironmentController()
    gamepads = GamepadsController()
    accounts = AccountsController()
    family = FamilyController()
    guest_account = GuestController()
    accessibility = AccessibilityController()
    power = PowerController()
    game_saves = GameSavesController()
    game_mode = GameModeController()
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
    restore_points = RestorePointsController()
    engine.rootContext().setContextProperty("updates", updates)
    engine.rootContext().setContextProperty("winUpdates", win_updates)
    engine.rootContext().setContextProperty("restorePoints", restore_points)
    engine.rootContext().setContextProperty("firmware", firmware)
    engine.rootContext().setContextProperty("remoteHelp", remote_help)
    engine.rootContext().setContextProperty("printers", printers)
    engine.rootContext().setContextProperty("kde", kde)
    engine.rootContext().setContextProperty("winprograms", winprograms)
    engine.rootContext().setContextProperty("services", services)
    engine.rootContext().setContextProperty("drivers", drivers)
    engine.rootContext().setContextProperty("health", health)
    engine.rootContext().setContextProperty("feedback", feedback)
    engine.rootContext().setContextProperty("disks", disks)
    engine.rootContext().setContextProperty("netfolders", netfolders)
    engine.rootContext().setContextProperty("sharing", sharing)
    engine.rootContext().setContextProperty("netlimit", netlimit)
    engine.rootContext().setContextProperty("backup", backup)
    engine.rootContext().setContextProperty("advanced", advanced)
    engine.rootContext().setContextProperty("reset", reset)
    engine.rootContext().setContextProperty("containers", containers)
    engine.rootContext().setContextProperty("environment", environment)
    engine.rootContext().setContextProperty("gamepads", gamepads)
    engine.rootContext().setContextProperty("accounts", accounts)
    engine.rootContext().setContextProperty("family", family)
    engine.rootContext().setContextProperty("guestAccount", guest_account)
    engine.rootContext().setContextProperty("accessibility", accessibility)
    engine.rootContext().setContextProperty("power", power)
    engine.rootContext().setContextProperty("gameSaves", game_saves)
    engine.rootContext().setContextProperty("gameMode", game_mode)
    engine.rootContext().setContextProperty("cloud", cloud)
    engine.rootContext().setContextProperty("games", games)
    engine.rootContext().setContextProperty("devpanel", devpanel)
    engine.rootContext().setContextProperty("guide", guide)
    engine.rootContext().setContextProperty("appearance", appearance)
    engine.rootContext().setContextProperty("startup", startup)
    engine.rootContext().setContextProperty("wifi", wifi)
    network = NetworkController()
    engine.rootContext().setContextProperty("network", network)
    installed_apps = AppsController()
    engine.rootContext().setContextProperty("installedApps", installed_apps)
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
