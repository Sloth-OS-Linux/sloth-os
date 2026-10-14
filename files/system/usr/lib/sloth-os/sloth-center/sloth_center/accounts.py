"""Fiók és biztonság: mihez kérjen jelszót a rendszer, automatikus bejelentkezés, sudo.

A beállítás témakörönként történik (programok telepítése, frissítés, …). A mentést a
sloth-helper végzi (admin-policy): polkit-szabályt, sudoers- és bejelentkezési beállítást ír,
mindig csak a hívó felhasználóra. Az állapotot a /etc/sloth-os/admin-policy.json-ból olvassuk
(jelszó nélkül olvasható, titkot nem tartalmaz).
"""
import getpass
import grp
import json
import logging
import subprocess

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


class AccountsController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user = getpass.getuser()
        self._admin = False
        self._free = []         # témakörök, amelyekhez nem kell jelszó
        self._sudo = False
        self._autologin = False
        self._error = ""
        self._info = ""
        self.refresh()

    userName = Property(str, lambda self: self._user, notify=changed)
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
        self.changed.emit()

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
