"""A Sloth OS telepítő vezérlője (QML <-> Python).

Lépések: welcome (nyelv) -> region (billentyűzet, időzóna) -> account (fiók) -> disk -> confirm -> install
-> done | error. A fiókot első induláskor a telepített rendszer hozza létre (sloth-first-user).
A tényleges telepítést a sloth-install-helper végzi rendszergazdaként (pkexec);
innen csak emberi nyelvű állapot és folyamatjelző látszik.
"""
import json
import logging
import os
import re
import unicodedata
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Property, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog

try:
    from PySide6.QtDBus import QDBusConnection, QDBusInterface
except ImportError:  # D-Bus nélkül is telepítünk, csak a képernyő lekapcsolását nem tudjuk tiltani
    QDBusConnection = None

from sloth_common.i18n import Catalog

from . import system

log = logging.getLogger("sloth-installer")

LOG_FILE = Path("/tmp/sloth-install.log")  # a sloth-install-helper írja

HELPER = "/usr/libexec/sloth-os/sloth-install-helper"
PAGES = ["welcome", "region", "account", "disk", "confirm", "install", "done", "error"]
NAV_PAGES = PAGES[:5]   # ezek között lehet előre-hátra lépni
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
GIB = 1024**3
MIN_BESIDE_GIB = 40   # Windows mellé legalább ennyi kell (a segédben is: MIN_BESIDE_BYTES)
RESERVED_USERS = {"root", "bin", "daemon", "adm", "lp", "sync", "shutdown", "halt", "mail", "operator",
                  "games", "ftp", "nobody", "dbus", "polkitd", "sddm", "plasmalogin", "liveuser", "admin",
                  "wheel", "users"}
# Telepítés közben ne kapcsoljon le a képernyő, ne zároljon és ne aludjon el a gép. A tiltás addig
# érvényes, amíg a telepítő fut (kilépéskor a D-Bus kapcsolattal együtt megszűnik).
INHIBITORS = [
    ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver"),
    ("org.freedesktop.PowerManagement.Inhibit", "/org/freedesktop/PowerManagement/Inhibit",
     "org.freedesktop.PowerManagement.Inhibit"),
]


def suggest_username(full_name):
    """"Kiss Anna" -> "anna": a keresztnév (utolsó szó) ékezetek nélkül, kisbetűvel."""
    for word in reversed(full_name.split()):
        plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
        plain = re.sub(r"[^a-z0-9_-]", "", plain)
        if plain[:1].isalpha():
            return plain[:32]
    return ""  # pl. cirill betűs név: a felhasználó maga írja be
catalog = Catalog(Path(__file__).resolve().parent / "translations")


class InstallerController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = "welcome"
        self._languages = system.languages()
        self._keyboards = system.keyboards()
        self._timezones = system.timezones()
        self._language = "en"
        self._keyboard = "us"
        self._timezone = "UTC"
        self._keyboard_chosen = False   # ha a felhasználó maga választott, a nyelvváltás nem írja felül
        self._timezone_chosen = False
        self._disks = []
        self._disk = ""
        self._confirmed = False
        self._full_name = ""
        self._username = ""
        self._username_edited = False   # ha a felhasználó maga írta, a név változása nem írja felül
        self._password = ""
        self._stage = ""
        self._progress = 0
        self._error = ""
        self._log_saved = ""   # hová mentette a felhasználó a telepítés naplóját (hibaoldal)
        self._proc = None
        self._buffer = b""
        # Windows mellé telepítés: a lemez felmérése (sloth-install-helper probe) és a választás
        self._beside = False
        self._probe = {}            # a segéd válasza; {"state": "probing"} amíg fut
        self._probe_proc = None
        self._size_gib = 0
        # Lemeztitkosítás (LUKS2): alapból a fiók jelszavával, de külön jelszó is adható
        self._encrypt = False
        self._encrypt_same = True
        self._encrypt_pw = ("", "")
        # A kiosztás élő átállítása kis késleltetéssel: a nyelvlistán végiglépkedve ne fusson
        # minden nyelvnél külön váltás (egymásra futva rossz kiosztás maradhatott érvényben)
        self._keyboard_timer = QTimer(self, singleShot=True, interval=400)
        self._keyboard_timer.timeout.connect(lambda: system.apply_live_keyboard(self._keyboard))
        start = catalog.system_language()
        self.setLanguage(start if any(l["code"] == start for l in self._languages) else "en")

    # --- Tulajdonságok -------------------------------------------------------------

    page = Property(str, lambda self: self._page, notify=changed)
    languages = Property("QVariantList", lambda self: self._languages, constant=True)
    keyboards = Property("QVariantList", lambda self: self._keyboards, constant=True)
    timezones = Property("QVariantList", lambda self: self._timezones, constant=True)
    language = Property(str, lambda self: self._language, notify=changed)
    keyboard = Property(str, lambda self: self._keyboard, notify=changed)
    timezone = Property(str, lambda self: self._timezone, notify=changed)
    disks = Property("QVariantList", lambda self: self._disks, notify=changed)
    disk = Property(str, lambda self: self._disk, notify=changed)
    confirmed = Property(bool, lambda self: self._confirmed, notify=changed)
    fullName = Property(str, lambda self: self._full_name, notify=changed)
    username = Property(str, lambda self: self._username, notify=changed)
    progress = Property(int, lambda self: self._progress, notify=changed)
    strings = Property("QVariantMap", lambda self: catalog.strings(), notify=changed)

    @Property(str, notify=changed)
    def statusText(self):
        return catalog.tr(f"stage.{self._stage}") if self._stage else ""

    @Property(str, notify=changed)
    def errorText(self):
        return catalog.tr(self._error) if self._error else ""

    beside = Property(bool, lambda self: self._beside, notify=changed)
    encrypt = Property(bool, lambda self: self._encrypt, notify=changed)
    encryptSame = Property(bool, lambda self: self._encrypt_same, notify=changed)

    def _passphrase(self):
        return self._password if self._encrypt_same else self._encrypt_pw[0]

    @Property(str, notify=changed)
    def encryptProblem(self):
        """Mi hiányzik a titkosításhoz (fordítási kulcs), vagy üres, ha rendben van."""
        if not self._encrypt:
            return ""
        if not self._encrypt_same and self._encrypt_pw[0] != self._encrypt_pw[1]:
            return "disk.encrypt.mismatch"
        if len(self._passphrase()) < 8:
            return "disk.encrypt.short_same" if self._encrypt_same else "disk.encrypt.short"
        return ""
    sizeGib = Property(int, lambda self: self._size_gib, notify=changed)

    @Property("QVariantMap", notify=changed)
    def besideInfo(self):
        """A Windows mellé telepítés lehetőségei a felületnek: állapot, határok, akadályok."""
        p = self._probe
        if not p:
            return {"state": "none"}
        if p.get("state") == "probing":
            return {"state": "probing"}
        problems = [x for x in p.get("problems", []) if x != "bitlocker"]
        max_gib = int(p.get("max", 0) // GIB)
        if p.get("bitlocker") and max_gib < MIN_BESIDE_GIB:
            problems.append("bitlocker")
        # MBR-es lemeznél ne az UEFI bekapcsolását tanácsoljuk (a régi módban telepített Windows nem indulna)
        problems.sort(key=lambda x: (x != "not_gpt", x != "not_uefi"))
        possible = not problems and max_gib >= MIN_BESIDE_GIB
        if not possible and not problems:
            problems = ["no_space"]
        return {"state": "ready", "possible": possible, "problems": problems[:1],
                "minGib": MIN_BESIDE_GIB, "maxGib": max_gib, "bitlocker": bool(p.get("bitlocker")),
                # a választott méretből ennyit veszünk el a Windowstól (0, ha a szabad hely elég)
                "shrinkGib": 0 if p.get("free", 0) >= self._size_gib * GIB else
                max(0, self._size_gib - int(p.get("free", 0) // GIB))}

    @Property("QVariantMap", notify=changed)
    def diskInfo(self):
        return next((d for d in self._disks if d["path"] == self._disk), {})

    # --- Választások -----------------------------------------------------------------

    @Slot(str)
    def setLanguage(self, code):
        lang = next((l for l in self._languages if l["code"] == code), None)
        if not lang:
            return
        self._language = code
        catalog.set_language(code)
        if not self._keyboard_chosen and self._keyboard != lang["keyboard"]:
            self._keyboard = lang["keyboard"]
            self._keyboard_timer.start()
        if not self._timezone_chosen:
            self._timezone = lang["timezone"]
        QApplication.setApplicationDisplayName(catalog.tr("app.title"))
        QApplication.setLayoutDirection(Qt.LayoutDirection.RightToLeft if catalog.is_rtl()
                                        else Qt.LayoutDirection.LeftToRight)
        self.changed.emit()

    @Slot(str)
    def setKeyboard(self, kbd):
        self._keyboard, self._keyboard_chosen = kbd, True
        self._keyboard_timer.start()
        self.changed.emit()

    @Slot(str)
    def setTimezone(self, tz):
        self._timezone, self._timezone_chosen = tz, True
        self.changed.emit()

    # --- Fiók ---------------------------------------------------------------------

    @Slot(str)
    def setFullName(self, name):
        self._full_name = " ".join(name.split())
        if not self._username_edited:
            self._username = suggest_username(self._full_name)
        self.changed.emit()

    @Slot(str)
    def setUsername(self, name):
        self._username, self._username_edited = name.strip().lower(), True
        self.changed.emit()

    @Slot(str, str, result=str)
    def accountError(self, password, again):
        """Üres szöveg, ha a fiók adatai jók; különben a hiba fordítási kulcsa."""
        if not self._full_name:
            return "account.error.name"
        if not USERNAME_RE.match(self._username) or self._username in RESERVED_USERS:
            return "account.error.username"
        if not password:
            return "account.error.password"
        if password != again:
            return "account.error.mismatch"
        return ""

    @Slot(str)
    def setPassword(self, password):
        self._password = password

    @Slot()
    def refreshDisks(self):
        try:
            self._disks = system.disks()
        except Exception as e:  # lsblk hiba: üres listát mutatunk, a felület szól
            log.error("lemezek: %s", e)
            self._disks = []
        usable = [d for d in self._disks if not d["tooSmall"]]
        if self._disk not in {d["path"] for d in usable}:
            # ha csak egy belső lemez van, azt előre kijelöljük
            internal = [d for d in usable if not d["removable"]]
            self._disk = internal[0]["path"] if len(internal) == 1 else ""
            self._beside, self._probe = False, {}
        if self.diskInfo.get("contents") == "windows" and not self._probe:
            self._start_probe()
        self.changed.emit()

    @Slot(str)
    def selectDisk(self, path):
        if any(d["path"] == path and not d["tooSmall"] for d in self._disks):
            if path != self._disk:
                self._beside, self._probe = False, {}
            self._disk = path
            self._confirmed = False
            if self.diskInfo.get("contents") == "windows" and not self._probe:
                self._start_probe()
            self.changed.emit()

    def _start_probe(self):
        """A Windows-os lemez felmérése a háttérben (a segéd rendszergazdaként olvassa a partíciókat)."""
        if self._probe_proc:
            self._probe_proc.kill()
        self._probe = {"state": "probing"}
        proc = QProcess(self)
        self._probe_proc = proc
        disk = self._disk

        def done(_code, _status):
            if self._probe_proc is not proc or self._disk != disk:
                return
            self._probe_proc = None
            try:
                lines = bytes(proc.readAllStandardOutput()).decode().strip().splitlines()
                result = json.loads(lines[-1]) if lines else {}
            except ValueError:
                result = {}
            if "error" in result or not result:
                log.warning("lemezfelmérés: %s", result)
                result = {"problems": ["unknown"]}
            log.info("lemezfelmérés: %s", result)
            self._probe = result
            info = self.besideInfo
            if info.get("possible"):
                # alapból Windows mellé, a hely fele, de legalább 80 GB (ha van annyi)
                self._beside = True
                self._size_gib = max(MIN_BESIDE_GIB, min(info["maxGib"], max(80, info["maxGib"] // 2)))
            self.changed.emit()

        proc.finished.connect(done)
        args = [HELPER, "probe", "--disk", disk]
        if os.environ.get("SLOTH_INSTALL_DRY_RUN") == "1":
            proc.start(HELPER, args[1:])
        else:
            proc.start("pkexec", args)

    @Slot(bool)
    def setBeside(self, value):
        if value and not self.besideInfo.get("possible"):
            return
        self._beside = value
        self._confirmed = False
        self.changed.emit()

    @Slot(bool)
    def setEncrypt(self, value):
        self._encrypt = value
        self._confirmed = False
        self.changed.emit()

    @Slot(bool)
    def setEncryptSame(self, value):
        self._encrypt_same = value
        self.changed.emit()

    @Slot(str, str)
    def setEncryptPassword(self, first, second):
        self._encrypt_pw = (first, second)
        self.changed.emit()

    @Slot(int)
    def setSizeGib(self, value):
        info = self.besideInfo
        if info.get("possible"):
            self._size_gib = max(info["minGib"], min(info["maxGib"], int(value)))
            self.changed.emit()

    @Slot(bool)
    def setConfirmed(self, value):
        self._confirmed = value
        self.changed.emit()

    # --- Navigáció ----------------------------------------------------------------------

    @Slot()
    def next(self):
        order = NAV_PAGES
        log.info("tovább: %s (lemez: %s)", self._page, self._disk or "-")
        if self._page in order[:-1]:
            self._page = order[order.index(self._page) + 1]
            if self._page == "disk":
                self.refreshDisks()
            self.changed.emit()

    @Slot()
    def back(self):
        order = NAV_PAGES
        log.info("vissza: %s", self._page)
        if self._page in order[1:]:
            self._page = order[order.index(self._page) - 1]
            self.changed.emit()

    @Slot()
    def install(self):
        log.info("telepítés indítása: %s, %s, %s, %s", self._disk, self._language, self._keyboard, self._timezone)
        if self._proc or not self._disk or not self._confirmed:
            return
        if self._beside and not self.besideInfo.get("possible"):
            return
        if self.encryptProblem:
            return
        locale = next(l["locale"] for l in self._languages if l["code"] == self._language)
        self._page, self._stage, self._progress, self._error = "install", "start", 0, ""
        self.changed.emit()
        self._inhibit_idle()
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._finished)
        args = [HELPER, "install", "--disk", self._disk, "--locale", locale,
                "--keyboard", self._keyboard, "--timezone", self._timezone,
                "--username", self._username, "--fullname", self._full_name]
        if self._beside:
            args += ["--beside-windows", "--size-gib", str(self._size_gib)]
        if self._encrypt:
            args.append("--encrypt")
        if os.environ.get("SLOTH_INSTALL_DRY_RUN") == "1":
            # próbaüzem: jelszókérés és lemeztörlés nélkül
            self._proc.start(HELPER, args[1:])
        else:
            self._proc.start("pkexec", args)
        # A jelszó a szabványos bemeneten megy át (parancssorban nem látszana el más folyamatoknak)
        self._proc.write((self._password + "\n").encode())
        if self._encrypt:
            # a titkosítás jelszava a második sor (szintén csak a szabványos bemeneten)
            self._proc.write((self._passphrase() + "\n").encode())
        self._proc.closeWriteChannel()

    def _inhibit_idle(self):
        if QDBusConnection is None or getattr(self, "_inhibited", False):
            return
        bus = QDBusConnection.sessionBus()
        for service, path, interface in INHIBITORS:
            reply = QDBusInterface(service, path, interface, bus).call("Inhibit", "Sloth OS", "Installing Sloth OS")
            if reply.arguments():
                self._inhibited = True
            else:
                log.warning("nem sikerült tiltani (%s): %s", service, reply.errorMessage())

    def _read(self):
        self._buffer += bytes(self._proc.readAllStandardOutput())
        *lines, self._buffer = self._buffer.split(b"\n")
        for raw in lines:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if "stage" in msg:
                self._stage = msg["stage"]
                self._progress = int(msg.get("progress", self._progress))
            elif msg.get("done"):
                self._progress, self._page = 100, "done"
            elif "error" in msg:
                self._error = msg["error"]
            self.changed.emit()

    def _finished(self, code, _status):
        self._proc = None
        if self._page == "done":
            return
        # 126/127: a jelszókérést megszakították vagy nem kaptunk jogot
        if not self._error:
            self._error = "error.not_authorized" if code in (126, 127) else "error.install_failed"
        self._page = "error"
        self.changed.emit()

    @Slot()
    def retry(self):
        self._page, self._error, self._log_saved = "confirm", "", ""
        self.changed.emit()

    @Property(str, notify=changed)
    def logSaved(self):
        return self._log_saved

    @Slot()
    def saveLog(self):
        """A telepítés naplója egy választott helyre (alapból egy bedugott pendrive-ra), hogy el lehessen küldeni."""
        start = next((d for d in sorted(Path("/run/media").glob("*/*")) if os.access(d, os.W_OK)), Path.home())
        path, _ = QFileDialog.getSaveFileName(None, catalog.tr("error.save_log"),
                                              str(start / "sloth-install.log"))
        if not path:
            return
        try:
            Path(path).write_bytes(LOG_FILE.read_bytes())
            os.sync()  # a pendrive-ot rögtön ki lehessen húzni
            self._log_saved = catalog.tr("error.log_saved", path=path)
        except OSError as e:
            log.warning("napló mentése: %s", e)
            self._log_saved = catalog.tr("error.log_save_failed")
        self.changed.emit()

    @Slot()
    def reboot(self):
        QProcess.startDetached("systemctl", ["reboot"])

    @Slot()
    def tryLive(self):
        """Kipróbálom: a választott nyelven jön fel az asztal, a telepítő bezárul."""
        if self._language != catalog.system_language():
            locale = next(l["locale"] for l in self._languages if l["code"] == self._language)
            system.apply_live_language(self._language, locale)
        QApplication.quit()

    @Slot()
    def quit(self):
        if not self._proc:
            QApplication.quit()
