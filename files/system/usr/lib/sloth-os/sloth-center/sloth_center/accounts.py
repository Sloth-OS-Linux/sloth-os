"""Fiók és biztonság: mihez kérjen jelszót a rendszer, automatikus bejelentkezés, sudo,
bejelentkezési módok (ujjlenyomat, biztonsági kulcs, céges fiók) a gép hardvere alapján.

A beállítás témakörönként történik (programok telepítése, frissítés, …). A mentést a
sloth-helper végzi (admin-policy): polkit-szabályt, sudoers- és bejelentkezési beállítást ír,
mindig csak a hívó felhasználóra. Az állapotot a /etc/sloth-os/admin-policy.json-ból olvassuk
(jelszó nélkül olvasható, titkot nem tartalmaz).
"""
import getpass
import grp
import json
import logging
import os
import re
import subprocess
import threading
from pathlib import Path

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import N_, tr

log = logging.getLogger("sloth-center.accounts")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
POLICY = "/etc/sloth-os/admin-policy.json"

# (azonosító, név, leírás, alapból védett-e). Az azonosítók a sloth-helper TOPICS kulcsai.
TOPICS = [
    ("software", N_("Programok telepítése és eltávolítása"), N_("Appok a Discoverből és a Sloth Üdvözlőből."), False),
    ("updates", N_("Rendszerfrissítés"), N_("Frissítések telepítése, visszaállás egy korábbi verzióra."), False),
    ("network", N_("Hálózat és eszközök"), N_("Wi-Fi, Bluetooth, nyomtatók, pendrive-ok."), False),
    ("datetime", N_("Dátum, idő és nyelv"), N_("Óra, időzóna, a rendszer nyelve, a gép neve."), False),
    ("services", N_("Szolgáltatások és driverek"), N_("Szolgáltatások be- és kikapcsolása, videókártya-driver váltása."), False),
    ("disks", N_("Lemezek"), N_("Lemezek formázása, partíciók. Egy rossz kattintással adat veszhet el."), True),
    ("users", N_("Felhasználók és jelszavak"), N_("Új fiók, más fiókok jelszava és jogai."), True),
    ("system", N_("Rendszerindítás és rendszercsomagok"), N_("Boot menü, kernelparaméterek, rendszercsomagok. Itt a legkönnyebb elrontani a rendszert."), True),
]
RECOMMENDED = [t[0] for t in TOPICS if not t[3]]

U2F_KEYS = Path.home() / ".config/Yubico/u2f_keys"
PIN_DIR = Path("/etc/sloth-os/pin")
UDEV_DATA = Path("/run/udev/data")


def _fingerprint_reader():
    """Van-e ujjlenyomat-olvasó (az fprintd szerint)."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        devices = bus.call_sync("net.reactivated.Fprint", "/net/reactivated/Fprint/Manager",
                                "net.reactivated.Fprint.Manager", "GetDevices", None,
                                GLib.VariantType("(ao)"), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
        return bool(devices)
    except GLib.Error:
        return False


def _security_key_present():
    """Be van-e dugva FIDO2 biztonsági kulcs (az udev ID_FIDO_TOKEN jelölése alapján)."""
    for dev in Path("/sys/class/hidraw").glob("hidraw*"):
        try:
            number = (dev / "dev").read_text().strip()
            if "E:ID_FIDO_TOKEN=1" in (UDEV_DATA / f"c{number}").read_text(errors="replace"):
                return True
        except OSError:
            continue
    return False


def _ir_camera():
    """Infrakamera (a Windows Hello-szerű arcfelismeréshez kellene)."""
    for dev in Path("/sys/class/video4linux").glob("video*"):
        try:
            name = (dev / "name").read_text().lower()
        except OSError:
            continue
        if re.search(r"\bir\b|infrared", name):
            return True
    return False


def _login_features():
    """A bekapcsolt authselect-funkciók (pl. "with-fingerprint")."""
    try:
        r = subprocess.run(["authselect", "current", "--raw"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return []
    return r.stdout.split()[1:] if r.returncode == 0 else []


def _domain():
    try:
        r = subprocess.run(["realm", "list", "--name-only"], capture_output=True, text=True, timeout=15)
        return r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


class AccountsController(QObject):
    changed = Signal()
    _enroll_done = Signal(bool, str)
    _join_done = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = getpass.getuser()
        self._admin = False
        self._free = []         # témakörök, amelyekhez nem kell jelszó
        self._sudo = False
        self._autologin = False
        self._error = ""
        self._info = ""
        self._methods = []
        self._domain = ""
        self._busy = ""         # "securitykey" (kulcs felvétele), "domain" (csatlakozás) vagy ""
        self._enroll_done.connect(self._on_enrolled)
        self._join_done.connect(self._on_joined)
        self.refresh()

    userName = Property(str, lambda self: self._user, notify=changed)
    loginMethods = Property("QVariantList", lambda self: list(self._methods), notify=changed)
    domain = Property(str, lambda self: self._domain, notify=changed)
    busyTask = Property(str, lambda self: self._busy, notify=changed)
    isAdmin = Property(bool, lambda self: self._admin, notify=changed)
    sudoWithoutPassword = Property(bool, lambda self: self._sudo, notify=changed)
    autologin = Property(bool, lambda self: self._autologin, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Property("QVariantList", notify=changed)
    def topics(self):
        return [{"id": t, "name": tr(name), "description": tr(desc), "risky": risky,
                 "passwordNeeded": t not in self._free} for t, name, desc, risky in TOPICS]

    @Property(str, notify=changed)
    def preset(self):
        """"all" (mindenhez kell jelszó), "recommended" (csak a fontosakhoz) vagy "custom"."""
        if not self._free:
            return "all"
        return "recommended" if sorted(self._free) == sorted(RECOMMENDED) else "custom"

    @Slot()
    def refresh(self):
        try:
            self._admin = self._user in grp.getgrnam("wheel").gr_mem
        except KeyError:
            self._admin = False
        try:
            cfg = json.load(open(POLICY, encoding="utf-8")).get("users", {}).get(self._user, {})
        except (OSError, ValueError):
            cfg = {}
        self._free = list(cfg.get("topics", []))
        self._sudo = bool(cfg.get("sudo"))
        self._autologin = bool(cfg.get("autologin"))
        self._methods = self._login_methods()
        self._domain = _domain()
        self.changed.emit()

    def _login_methods(self):
        """A gépen elérhető bejelentkezési módok: csak az látszik, amihez megvan a hardver."""
        features = _login_features()
        out = []
        if _fingerprint_reader():
            out.append({"id": "fingerprint", "name": tr("Ujjlenyomat"), "icon": "fingerprint",
                        "description": tr("Bejelentkezés és jóváhagyás az ujjad érintésével. Előbb vedd fel az ujjlenyomatod."),
                        "enabled": "with-fingerprint" in features, "ready": True})
        enrolled = U2F_KEYS.exists() and U2F_KEYS.stat().st_size > 0
        if enrolled or _security_key_present():
            out.append({"id": "securitykey", "name": tr("Biztonsági kulcs (pl. YubiKey)"), "icon": "security-high",
                        "description": tr("Bejelentkezés a kulcs bedugásával és megérintésével.")
                        if enrolled else tr("Bedugott kulcsot találtunk. Vedd fel, és utána bejelentkezhetsz vele."),
                        "enabled": "with-pam-u2f" in features, "ready": enrolled})
        if _ir_camera():
            out.append({"id": "face", "name": tr("Arcfelismerés"), "icon": "camera-web",
                        "description": tr("A gépeden van infrakamera. Az arcfelismerést még nem kínáljuk: "
                                          "a Linuxos megoldások ma még nem elég megbízhatók ahhoz, hogy a gépedet "
                                          "rájuk bízzuk. Addig használd a PIN-kódot vagy az ujjlenyomatot."),
                        "enabled": False, "ready": False, "comingSoon": True})
        pin = (PIN_DIR / f"{self._user}.json").exists()
        out.append({"id": "pin", "name": tr("PIN-kód"), "icon": "dialog-password",
                    "description": tr("Be van állítva. A bejelentkezésnél és a zárolási képernyőn a jelszó helyett "
                                      "a PIN-kódot is beírhatod. Távolról (hálózaton át) csak a jelszó működik.")
                    if pin else tr("Rövid számkód (4–8 számjegy) a hosszú jelszó helyett, a bejelentkezésnél "
                                   "és a zárolási képernyőn. A jelszó mellette továbbra is működik."),
                    "enabled": pin, "ready": True})
        return out

    def _helper(self, args, stdin=None):
        try:
            r = subprocess.run(["pkexec", HELPER, *args], input=stdin, capture_output=True, text=True, timeout=300)
            return json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("%s: %s", args[0], e)
            return {}

    @Slot(str, bool)
    def setLoginMethod(self, method, enabled):
        self._error, self._info = "", ""
        if method in ("fingerprint", "securitykey"):
            result = self._helper(["login-feature", method, "on" if enabled else "off"])
            if result.get("error"):
                log.warning("login-feature %s: %s", method, result["error"])
            if result.get("ok"):
                self._info = tr("Elmentve. A következő bejelentkezéstől érvényes.")
            else:
                self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    @Slot(str, str)
    def setPin(self, pin, pin2):
        """PIN-kód beállítása vagy cseréje a saját fióknak (4–8 számjegy)."""
        self._error, self._info = "", ""
        if not re.fullmatch(r"\d{4,8}", pin):
            self._error = tr("A PIN-kód 4–8 számjegyből álljon.")
        elif pin != pin2:
            self._error = tr("A két PIN-kód nem egyezik.")
        else:
            result = self._helper(["pin-set"], stdin=pin + "\n")
            if result.get("ok"):
                self._info = tr("A PIN-kód elmentve. A következő bejelentkezéstől használhatod.")
            elif result.get("error") == "gyenge PIN":
                self._error = tr("Ezt a PIN-kódot túl könnyű kitalálni (pl. 1111 vagy 1234). Válassz másikat.")
            else:
                self._error = tr("Nem sikerült menteni. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    @Slot()
    def removePin(self):
        self._error, self._info = "", ""
        if self._helper(["pin-remove"]).get("ok"):
            self._info = tr("A PIN-kód törölve. Mostantól csak a jelszó működik.")
        else:
            self._error = tr("Nem sikerült törölni. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    @Slot()
    def enrollSecurityKey(self):
        """Kulcs felvétele: a pamu2fcfg megvárja, hogy a felhasználó megérintse a kulcsot."""
        if self._busy:
            return
        self._busy, self._error, self._info = "securitykey", "", ""
        self.changed.emit()
        existing = U2F_KEYS.read_text().strip() if U2F_KEYS.exists() else ""

        def work():
            # Ha már van kulcs, a -n csak a kulcs adatait adja (a sor végére fűzzük)
            cmd = ["pamu2fcfg"] + (["-n"] if existing else [])
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                ok, out = r.returncode == 0 and r.stdout.strip(), r.stdout.strip()
            except (OSError, subprocess.SubprocessError) as e:
                ok, out = False, str(e)
            self._enroll_done.emit(bool(ok), out)
        threading.Thread(target=work, daemon=True).start()

    def _on_enrolled(self, ok, out):
        self._busy = ""
        if ok:
            U2F_KEYS.parent.mkdir(parents=True, exist_ok=True)
            existing = U2F_KEYS.read_text().strip() if U2F_KEYS.exists() else ""
            U2F_KEYS.write_text((existing + out if existing else out) + "\n")
            os.chmod(U2F_KEYS, 0o600)
            self._info = tr("A kulcs felvéve. Most bekapcsolhatod a bejelentkezést vele.")
        else:
            log.warning("pamu2fcfg: %s", out)
            self._error = tr("Nem sikerült felvenni a kulcsot. Dugd be, és amikor villog, érintsd meg.")
        self.refresh()

    @Slot(str, str, str)
    def joinDomain(self, domain, admin, password):
        """Csatlakozás céges (Active Directory) tartományhoz; a jelszót csak a realm kapja meg."""
        if self._busy:
            return
        self._busy, self._error, self._info = "domain", "", ""
        self.changed.emit()
        args = ["domain-join", domain.strip(), admin.strip()]
        threading.Thread(target=lambda: self._join_done.emit(self._helper(args, stdin=password + "\n")),
                         daemon=True).start()

    def _on_joined(self, result):
        self._busy = ""
        if result.get("ok"):
            self._info = tr("A gép csatlakozott a tartományhoz. A céges fiókkal a bejelentkező képernyőn léphetsz be (felhasználónév@tartomány).")
        elif not result:
            self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        else:
            log.warning("realm join: %s", result.get("error"))
            self._error = tr("Nem sikerült csatlakozni. Ellenőrizd a tartomány nevét, a felhasználónevet és a jelszót, és hogy a gép eléri-e a céges hálózatot.")
        self.refresh()

    @Slot()
    def leaveDomain(self):
        self._error, self._info = "", ""
        if self._helper(["domain-leave"]).get("ok"):
            self._info = tr("A gép kilépett a tartományból.")
        else:
            self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    def _save(self, free, sudo, autologin):
        self._error, self._info = "", ""
        request = json.dumps({"topics": free, "sudo": sudo, "autologin": autologin})
        try:
            r = subprocess.run(["pkexec", HELPER, "admin-policy"], input=request,
                               capture_output=True, text=True, timeout=120)
            result = json.loads(r.stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("admin-policy: %s", e)
            result = {}
        if result.get("ok"):
            self._info = tr("Elmentve.")
        elif result.get("error") == "nem rendszergazda":
            self._error = tr("Ezt csak rendszergazda fiókkal lehet bekapcsolni.")
        else:
            self._error = tr("Nem sikerült átállítani. Ehhez rendszergazdai jóváhagyás kell.")
        self.refresh()

    @Slot(str)
    def applyPreset(self, preset):
        free = {"all": [], "recommended": RECOMMENDED}.get(preset)
        if free is not None:
            self._save(free, self._sudo, self._autologin)

    @Slot(str, bool)
    def setPasswordNeeded(self, topic, needed):
        free = set(self._free)
        if needed:
            free.discard(topic)
        else:
            free.add(topic)
        self._save(sorted(free), self._sudo, self._autologin)

    @Slot(bool)
    def setSudoWithoutPassword(self, value):
        self._save(self._free, value, self._autologin)

    @Slot(bool)
    def setAutologin(self, value):
        self._save(self._free, self._sudo, value)

    @Slot()
    def openUsers(self):
        """A KDE Felhasználók beállítása: jelszó, rendszergazdai jog, új fiók."""
        try:
            subprocess.Popen(["systemsettings", "kcm_users"])
        except OSError as e:
            log.warning("kcm_users: %s", e)
