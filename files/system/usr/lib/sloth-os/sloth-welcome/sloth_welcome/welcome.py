"""Az üdvözlő varázsló vezérlője (QML <-> Python)."""
import grp
import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication

from sloth_common import sharing

from . import catalog, desktop, i18n
from .i18n import tr
from .installer import Installer

log = logging.getLogger("sloth-welcome")

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os"
DONE_MARKER = CONFIG_DIR / "welcome-done"

# A StackLayout lapjai a QML-ben. A kategóriák egy közös lapot használnak,
# a lépéssorrend: üdvözlés, megjelenés, jelszavak, megosztás, kategóriánként egy lépés, telepítés, kész.
STEAM = "com.valvesoftware.Steam"  # nincs előtelepítve: a Játékok lépésben választható

PAGE_WELCOME, PAGE_LOOK, PAGE_CATEGORY, PAGE_INSTALL, PAGE_DONE, PAGE_SECURITY, PAGE_SHARING = range(7)
STEPS = (["welcome", "look", "security", "sharing"] + [f"cat{i}" for i in range(len(catalog.CATEGORIES))]
         + ["install", "done"])

# Jelszavak: a "csak a kockázatos dolgokhoz" választásnál ezekhez nem kell jelszó (a Sloth Központ
# Fiók és biztonság oldalán témakörönként is állítható; a mentést a sloth-helper admin-policy végzi)
HELPER = "/usr/libexec/sloth-os/sloth-helper"
EASY_TOPICS = ["software", "updates", "network", "datetime", "services"]


def apply_language():
    """Ablakcím és írásirány a választott nyelvhez (arab, héber: jobbról balra, tükrözve)."""
    QApplication.setApplicationDisplayName(tr("app.title"))
    QApplication.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl()
                                    else Qt.LayoutDirection.LeftToRight)


class WelcomeController(QObject):
    changed = Signal()
    # A telepítő szálából érkező jelzések (Qt átteszi őket a fő szálra)
    _status_sig = Signal(str, str, int)
    _app_sig = Signal(str, str, str)
    _done_sig = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self._selected = []
        self._scheme = "SlothSilverDark"
        self._layout = "windows10"
        self._status = ""
        self._detail = ""
        self._progress = -1
        self._app_states = {}
        self._summary = ""          # fordítási kulcs
        self._failures = []         # [(név, hibakulcs)]
        self._online = desktop.is_online()
        self._installed = []
        self._security = "all"      # "all" (mindenhez jelszó) vagy "recommended"
        self._autologin = False
        self._security_saved = ("all", False)
        # Tapasztalatok megosztása (sloth_common/sharing.py): "" amíg nem választott, "yes" / "no"
        self._sharing = ("yes" if sharing.enabled() else "no") if sharing.CONFIG.exists() else ""
        self._status_sig.connect(self._on_status)
        self._app_sig.connect(self._on_app_state)
        self._done_sig.connect(self._on_done)
        self._installer = Installer(self._status_sig.emit, self._app_sig.emit, self._done_sig.emit)

    # --- Tulajdonságok ------------------------------------------------------

    def _step_name(self):
        return STEPS[self._step]

    @Property(int, notify=changed)
    def page(self):
        name = self._step_name()
        if name.startswith("cat"):
            return PAGE_CATEGORY
        return {"welcome": PAGE_WELCOME, "look": PAGE_LOOK, "security": PAGE_SECURITY, "sharing": PAGE_SHARING,
                "install": PAGE_INSTALL, "done": PAGE_DONE}[name]

    @Property(int, notify=changed)
    def categoryIndex(self):
        name = self._step_name()
        return int(name[3:]) if name.startswith("cat") else -1

    @Property(bool, notify=changed)
    def lastCategory(self):
        return self._step_name() == f"cat{len(catalog.CATEGORIES) - 1}"

    @Property(int, constant=True)
    def stepCount(self):
        return len(STEPS) - 2  # a telepítés és a kész oldal nem kérdés

    @Property(int, notify=changed)
    def stepNumber(self):
        return min(self._step + 1, len(STEPS) - 2)

    @Property("QVariantList", notify=changed)
    def selectedInCategory(self):
        i = self.categoryIndex
        if i < 0:
            return []
        ids = {a["id"] for a in catalog.CATEGORIES[i]["apps"]}
        return [a for a in self._selected if a in ids]

    # --- Nyelv ---------------------------------------------------------------
    # A QML a szövegeket a "strings" térképből veszi; nyelvváltáskor minden felirat frissül.

    @Property("QVariantList", constant=True)
    def languages(self):
        return i18n.available()

    @Property(str, notify=changed)
    def language(self):
        return i18n.language()

    @Property("QVariantMap", notify=changed)
    def strings(self):
        return i18n.strings()

    @Slot(str)
    def setLanguage(self, code):
        if code != i18n.language():
            i18n.set_language(code)
            apply_language()
            self.changed.emit()

    # --- Listák (a választott nyelven) ----------------------------------------

    @Property("QVariantList", notify=changed)
    def categories(self):
        out = []
        for cat in catalog.CATEGORIES:
            apps = [{**a, "summary": tr(f"app.{a['id']}"),
                     "iconUrl": f"file://{catalog.ICON_DIR}/{a['id']}.png"} for a in cat["apps"]]
            out.append({**cat, "name": tr(f"category.{cat['id']}.name"),
                        "hint": tr(f"category.{cat['id']}.hint"), "apps": apps})
        return out

    @Property("QVariantList", notify=changed)
    def schemes(self):
        return [{**s, "name": tr(f"scheme.{s['id']}")} for s in desktop.COLOR_SCHEMES]

    @Property("QVariantList", notify=changed)
    def layouts(self):
        return [{**l, "name": tr(f"layout.{l['id']}.name"), "description": tr(f"layout.{l['id']}.description")}
                for l in desktop.LAYOUTS]

    @Property(str, notify=changed)
    def currentLayout(self):
        return self._layout

    @Property("QVariantList", notify=changed)
    def selectedIds(self):
        return list(self._selected)

    @Property(str, notify=changed)
    def currentScheme(self):
        return self._scheme

    @Property(str, notify=changed)
    def statusText(self):
        return self._status

    @Property(str, notify=changed)
    def detailText(self):
        return self._detail

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property("QVariantMap", notify=changed)
    def appStates(self):
        return dict(self._app_states)

    @Property(str, notify=changed)
    def summaryText(self):
        return tr(self._summary) if self._summary else ""

    @Property("QVariantList", notify=changed)
    def failures(self):
        return [{"name": name, "error": tr(err)} for name, err in self._failures]

    @Property(bool, notify=changed)
    def online(self):
        return self._online

    @Property(bool, notify=changed)
    def steamInstalled(self):
        """A "Bejelentkezés a Steambe" gomb csak akkor látszik, ha a Steam most települt."""
        return STEAM in self._installed

    @Property(bool, notify=changed)
    def hasBrowser(self):
        browsers = {a["id"] for a in catalog.CATEGORIES[0]["apps"]}
        return any(a in browsers for a in self._selected)

    # --- Jelszavak ------------------------------------------------------------

    @Property(bool, constant=True)
    def isAdmin(self):
        try:
            return os.environ.get("USER", "") in grp.getgrnam("wheel").gr_mem
        except KeyError:
            return False

    @Property(str, notify=changed)
    def securityChoice(self):
        return self._security

    @Property(bool, notify=changed)
    def autologin(self):
        return self._autologin

    @Slot(str)
    def setSecurityChoice(self, choice):
        if choice in ("all", "recommended"):
            self._security = choice
            self.changed.emit()

    @Slot(bool)
    def setAutologin(self, value):
        self._autologin = value
        self.changed.emit()

    @Property(str, notify=changed)
    def sharingChoice(self):
        return self._sharing

    @Slot(str)
    def setSharingChoice(self, choice):
        if choice in ("yes", "no"):
            self._sharing = choice
            self.changed.emit()

    def _save_security(self):
        """A választás mentése (a háttérben; a jelszókérő ablakot a polkit mutatja)."""
        wanted = (self._security, self._autologin)
        if wanted == self._security_saved:
            return
        self._security_saved = wanted
        request = json.dumps({"topics": EASY_TOPICS if self._security == "recommended" else [],
                              "sudo": False, "autologin": self._autologin})

        def work():
            try:
                r = subprocess.run(["pkexec", HELPER, "admin-policy"], input=request,
                                   capture_output=True, text=True, timeout=600)
                log.info("jelszó-beállítás: %s", r.stdout.strip() or r.stderr.strip())
            except (OSError, subprocess.SubprocessError) as e:
                log.warning("jelszó-beállítás: %s", e)
        threading.Thread(target=work, daemon=True).start()

    # --- Navigáció ----------------------------------------------------------

    @Slot()
    def next(self):
        if self._step_name() == "security":
            self._save_security()
        if self._step_name() == "sharing":
            if not self._sharing:
                return  # választani kell (a gomb addig nem aktív)
            sharing.set_enabled(self._sharing == "yes")
        if self.lastCategory:
            self.install()
            return
        if self._step_name() not in ("install", "done"):
            self._step += 1
            if self._step_name() == "cat0":
                self._online = desktop.is_online()
            self.changed.emit()

    @Slot()
    def back(self):
        if 0 < self._step and self._step_name() not in ("install", "done"):
            self._step -= 1
            self.changed.emit()

    @Slot(str)
    def toggle(self, app_id):
        if app_id in self._selected:
            self._selected.remove(app_id)
        else:
            self._selected.append(app_id)
        self.changed.emit()

    @Slot(str)
    def setScheme(self, scheme_id):
        if scheme_id != self._scheme and desktop.apply_color_scheme(scheme_id):
            self._scheme = scheme_id
            self.changed.emit()

    @Slot(str)
    def setLayout(self, layout_id):
        if layout_id != self._layout and desktop.apply_layout(layout_id):
            self._layout = layout_id
            self.changed.emit()

    @Slot(str)
    def quickAction(self, name):
        desktop.quick_action(name)

    @Slot()
    def recheckOnline(self):
        self._online = desktop.is_online()
        self.changed.emit()

    @Slot()
    def openNetworkSettings(self):
        desktop.open_network_settings()

    @Slot()
    def install(self):
        if not self._selected:
            self._summary = "done.nothing_selected"
            self._step = STEPS.index("done")
            self.changed.emit()
            return
        self._step = STEPS.index("install")
        self._status = tr("install.preparing")
        self._app_states = {a: "waiting" for a in self._selected}
        self.changed.emit()
        self._installer.start(self._selected)

    @Property(bool, notify=changed)
    def anyInstalled(self):
        return bool(self._installed)

    @Slot(bool)
    def finish(self, restart=False):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DONE_MARKER.touch()
        if self._installed and not restart:
            desktop.refresh_app_cache()
        # A telepített böngészők és a Steam a tálcára kerülnek. A már meglévő böngésző is
        # (a telepítő internet nélkül átmásolja az élő rendszer Firefoxát)
        browsers = [a["id"] for a in catalog.CATEGORIES[0]["apps"]]
        present = [a for a in browsers if Path("/var/lib/flatpak/app", a).is_dir()]
        desktop.pin_to_taskbar([a for a in self._installed if a in browsers or a == STEAM]
                               + [a for a in present if a not in self._installed])
        if restart:
            desktop.reboot()
        QApplication.quit()

    # --- A telepítő jelzései -------------------------------------------------

    def _on_status(self, text, detail, pct):
        self._status, self._detail, self._progress = text, detail, pct
        self.changed.emit()

    def _on_app_state(self, app_id, state, _error):
        self._app_states[app_id] = state
        self.changed.emit()

    def _on_done(self, ok, failed):
        self._installed = list(ok)
        self._failures = [((catalog.find_app(a) or {}).get("name", a), err) for a, err in failed.items()]
        if not failed:
            self._summary = "done.all_ok"
        elif ok:
            self._summary = "done.some_failed"
        else:
            self._summary = "done.all_failed"
        self._progress = 100
        self._step = STEPS.index("done")
        self.changed.emit()
