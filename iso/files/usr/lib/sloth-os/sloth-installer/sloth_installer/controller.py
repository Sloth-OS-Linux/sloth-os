"""Controller of the Sloth OS installer (QML <-> Python).

Steps: welcome (language) -> region (keyboard, time zone) -> account -> disk -> confirm -> install
-> done | error. The account is created on first boot by the installed system (sloth-first-user).
The actual install is done by sloth-install-helper as administrator (pkexec);
from here only a human-language status and a progress bar are visible.
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
except ImportError:  # we install without D-Bus too, we just cannot prevent the screen from turning off
    QDBusConnection = None

from sloth_common.i18n import Catalog

from . import system

log = logging.getLogger("sloth-installer")

LOG_FILE = Path("/tmp/sloth-install.log")  # written by sloth-install-helper

HELPER = "/usr/libexec/sloth-os/sloth-install-helper"
PAGES = ["welcome", "region", "account", "disk", "confirm", "install", "done", "error"]
NAV_PAGES = PAGES[:5]   # one can step back and forth between these
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
GIB = 1024**3
MIN_BESIDE_GIB = 40   # next to Windows at least this much is needed (in the helper too: MIN_BESIDE_BYTES)
RESERVED_USERS = {"root", "bin", "daemon", "adm", "lp", "sync", "shutdown", "halt", "mail", "operator",
                  "games", "ftp", "nobody", "dbus", "polkitd", "sddm", "plasmalogin", "liveuser", "admin",
                  "wheel", "users"}
# While installing, the screen must not turn off, lock, or the machine go to sleep. The inhibition holds
# while the installer runs (it ends together with the D-Bus connection on exit).
INHIBITORS = [
    ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "org.freedesktop.ScreenSaver"),
    ("org.freedesktop.PowerManagement.Inhibit", "/org/freedesktop/PowerManagement/Inhibit",
     "org.freedesktop.PowerManagement.Inhibit"),
]


def suggest_username(full_name):
    """"Kiss Anna" -> "anna": the last word (the given name in Hungarian order), without accents, lowercase."""
    for word in reversed(full_name.split()):
        plain = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()
        plain = re.sub(r"[^a-z0-9_-]", "", plain)
        if plain[:1].isalpha():
            return plain[:32]
    return ""  # e.g. a name in Cyrillic letters: the user types it
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
        self._keyboard_chosen = False   # if the user chose it, a language change does not overwrite it
        self._timezone_chosen = False
        self._disks = []
        self._disk = ""
        self._confirmed = False
        self._full_name = ""
        self._username = ""
        self._username_edited = False   # if the user typed it, a change of the name does not overwrite it
        self._password = ""
        self._stage = ""
        self._progress = 0
        self._error = ""
        self._log_saved = ""   # where the user saved the install log (error page)
        self._proc = None
        self._buffer = b""
        # Installing next to Windows: surveying the disk (sloth-install-helper probe) and the choice
        self._beside = False
        self._probe = {}            # the helper's answer; {"state": "probing"} while it runs
        self._probe_proc = None
        self._size_gib = 0
        # Disk encryption (LUKS2): by default with the account's password, but a separate one can be given
        self._encrypt = False
        self._encrypt_same = True
        self._encrypt_pw = ("", "")
        # The other internal disks: {path: "leave" | "keep" | "erase"}; by default they are not touched
        self._extra = {}
        # Switching the layout live with a small delay: stepping through the language list must not
        # switch for every language (overlapping switches could leave a wrong layout active)
        self._keyboard_timer = QTimer(self, singleShot=True, interval=400)
        self._keyboard_timer.timeout.connect(lambda: system.apply_live_keyboard(self._keyboard))
        start = catalog.system_language()
        self.setLanguage(start if any(l["code"] == start for l in self._languages) else "en")

    # --- Properties -------------------------------------------------------------

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
        """What is missing for encryption (translation key), or empty if it is fine."""
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
        """The options for installing next to Windows, for the UI: state, limits, obstacles."""
        p = self._probe
        if not p:
            return {"state": "none"}
        if p.get("state") == "probing":
            return {"state": "probing"}
        problems = [x for x in p.get("problems", []) if x != "bitlocker"]
        max_gib = int(p.get("max", 0) // GIB)
        if p.get("bitlocker") and max_gib < MIN_BESIDE_GIB:
            problems.append("bitlocker")
        # On an MBR disk do not advise turning on UEFI (Windows installed in the old mode would not start)
        problems.sort(key=lambda x: (x != "not_gpt", x != "not_uefi"))
        possible = not problems and max_gib >= MIN_BESIDE_GIB
        if not possible and not problems:
            problems = ["no_space"]
        windows = p.get("windows") or {}
        shrink_gib = 0
        shrink_bytes = 0
        if windows and p.get("free", 0) < self._size_gib * GIB:
            shrink_bytes = max(0, self._size_gib * GIB - windows.get("after", 0))
            shrink_gib = (shrink_bytes + GIB - 1) // GIB
        before_gib = int(windows.get("size", 0) // GIB)
        return {"state": "ready", "possible": possible, "problems": problems[:1],
                "minGib": MIN_BESIDE_GIB, "maxGib": max_gib, "bitlocker": bool(p.get("bitlocker")),
                "shrinkGib": shrink_gib, "windowsPath": windows.get("path", ""),
                "windowsBeforeGib": before_gib,
                "windowsAfterGib": int(max(0, windows.get("size", 0) - shrink_bytes) // GIB)}

    @Property("QVariantList", notify=changed)
    def extraDisks(self):
        """The internal disks besides the target, with what may be done to them. A disk with Windows data (NTFS,
        BitLocker) can only be left alone; "keep" needs a Linux file system on it."""
        out = []
        for d in self._disks:
            if d["path"] == self._disk or d["removable"]:
                continue
            windows = d["contents"] == "windows"
            out.append({**d, "choice": self._extra.get(d["path"], "leave"),
                        "canKeep": d.get("mountable", False) and not windows, "canErase": not windows})
        return out

    @Slot(str, str)
    def setExtraChoice(self, path, choice):
        disk = next((d for d in self.extraDisks if d["path"] == path), None)
        if not disk or choice not in ("leave", "keep", "erase") \
                or (choice == "keep" and not disk["canKeep"]) or (choice == "erase" and not disk["canErase"]):
            return
        self._extra[path] = choice
        self._confirmed = False
        self.changed.emit()

    def _extra_args(self):
        allowed = {d["path"]: d for d in self.extraDisks}
        args = []
        for path, choice in self._extra.items():
            d = allowed.get(path)
            if d and ((choice == "keep" and d["canKeep"]) or (choice == "erase" and d["canErase"])):
                args += ["--extra-disk", f"{choice}:{path}"]
        return args

    @Property("QVariantMap", notify=changed)
    def diskInfo(self):
        return next((d for d in self._disks if d["path"] == self._disk), {})

    # --- Choices -----------------------------------------------------------------

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

    # --- Account ---------------------------------------------------------------------

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
        """Empty text if the account details are fine; otherwise the error's translation key."""
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
        except Exception as e:  # lsblk error: we show an empty list, the UI says so
            log.error("lemezek: %s", e)
            self._disks = []
        usable = [d for d in self._disks if not d["tooSmall"]]
        if self._disk not in {d["path"] for d in usable}:
            # if there is only one internal disk, it is selected in advance
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
            self._extra.pop(path, None)   # the target is not an "other disk" any more
            self._confirmed = False
            if self.diskInfo.get("contents") == "windows" and not self._probe:
                self._start_probe()
            self.changed.emit()

    def _start_probe(self):
        """Surveys the Windows disk in the background (the helper reads the partitions as administrator)."""
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
                log.warning("disk survey: %s", result)
                result = {"problems": ["unknown"]}
            log.info("disk survey: %s", result)
            self._probe = result
            info = self.besideInfo
            if info.get("possible"):
                # by default next to Windows, half of the space, but at least 80 GB (if there is that much)
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

    # --- Navigation ----------------------------------------------------------------------

    @Slot()
    def next(self):
        order = NAV_PAGES
        log.info("next: %s (disk: %s)", self._page, self._disk or "-")
        if self._page in order[:-1]:
            self._page = order[order.index(self._page) + 1]
            if self._page == "disk":
                self.refreshDisks()
            self.changed.emit()

    @Slot()
    def back(self):
        order = NAV_PAGES
        log.info("back: %s", self._page)
        if self._page in order[1:]:
            self._page = order[order.index(self._page) - 1]
            self.changed.emit()

    @Slot()
    def install(self):
        log.info("starting the install: %s, %s, %s, %s", self._disk, self._language, self._keyboard, self._timezone)
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
        extra = self._extra_args()
        if extra:
            args += extra + ["--data-label", catalog.tr("disk.extra.label")]
        if os.environ.get("SLOTH_INSTALL_DRY_RUN") == "1":
            # dry run: without password prompt and erasing the disk
            self._proc.start(HELPER, args[1:])
        else:
            self._proc.start("pkexec", args)
        # The password goes through standard input (on the command line it would be visible to other processes)
        self._proc.write((self._password + "\n").encode())
        if self._encrypt:
            # the encryption password is the second line (also only on standard input)
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
                log.warning("could not inhibit (%s): %s", service, reply.errorMessage())

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
        # 126/127: the password prompt was cancelled or we were not given permission
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
        """Saves the install log to a chosen place (by default a plugged-in USB stick), so it can be sent."""
        start = next((d for d in sorted(Path("/run/media").glob("*/*")) if os.access(d, os.W_OK)), Path.home())
        path, _ = QFileDialog.getSaveFileName(None, catalog.tr("error.save_log"),
                                              str(start / "sloth-install.log"))
        if not path:
            return
        try:
            Path(path).write_bytes(LOG_FILE.read_bytes())
            os.sync()  # so the USB stick can be pulled out right away
            self._log_saved = catalog.tr("error.log_saved", path=path)
        except OSError as e:
            log.warning("saving the log: %s", e)
            self._log_saved = catalog.tr("error.log_save_failed")
        self.changed.emit()

    @Slot()
    def reboot(self):
        QProcess.startDetached("systemctl", ["reboot"])

    @Slot()
    def tryLive(self):
        """Try it: the desktop comes up in the chosen language, the installer closes."""
        if self._language != catalog.system_language():
            locale = next(l["locale"] for l in self._languages if l["code"] == self._language)
            system.apply_live_language(self._language, locale)
        QApplication.quit()

    @Slot()
    def quit(self):
        if not self._proc:
            QApplication.quit()
