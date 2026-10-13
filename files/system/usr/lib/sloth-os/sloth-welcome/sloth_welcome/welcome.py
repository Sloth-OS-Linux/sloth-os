"""Az üdvözlő varázsló vezérlője (QML <-> Python)."""
import logging
import os
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtWidgets import QApplication

from . import catalog, desktop
from .installer import Installer

log = logging.getLogger("sloth-welcome")

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os"
DONE_MARKER = CONFIG_DIR / "welcome-done"

# A StackLayout lapjai a QML-ben. A kategóriák egy közös lapot használnak,
# a lépéssorrend: üdvözlés, megjelenés, kategóriánként egy lépés, telepítés, kész.
PAGE_WELCOME, PAGE_LOOK, PAGE_CATEGORY, PAGE_INSTALL, PAGE_DONE = range(5)
STEPS = (["welcome", "look"] + [f"cat{i}" for i in range(len(catalog.CATEGORIES))]
         + ["install", "done"])


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
        self._summary = ""
        self._failures = []
        self._online = desktop.is_online()
        self._installed = []
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
        return {"welcome": PAGE_WELCOME, "look": PAGE_LOOK, "install": PAGE_INSTALL, "done": PAGE_DONE}[name]

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

    @Property("QVariantList", constant=True)
    def categories(self):
        out = []
        for cat in catalog.CATEGORIES:
            apps = [{**a, "iconUrl": f"file://{catalog.ICON_DIR}/{a['id']}.png"} for a in cat["apps"]]
            out.append({**cat, "apps": apps})
        return out

    @Property("QVariantList", constant=True)
    def schemes(self):
        return desktop.COLOR_SCHEMES

    @Property("QVariantList", constant=True)
    def layouts(self):
        return desktop.LAYOUTS

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
        return self._summary

    @Property("QVariantList", notify=changed)
    def failures(self):
        return list(self._failures)

    @Property(bool, notify=changed)
    def online(self):
        return self._online

    @Property(bool, notify=changed)
    def hasBrowser(self):
        browsers = {a["id"] for a in catalog.CATEGORIES[0]["apps"]}
        return any(a in browsers for a in self._selected)

    # --- Navigáció ----------------------------------------------------------

    @Slot()
    def next(self):
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
            self._summary = "Kész is vagyunk! Appokat később is telepíthetsz a Discoverben."
            self._step = STEPS.index("done")
            self.changed.emit()
            return
        self._step = STEPS.index("install")
        self._status = "Felkészülés a telepítésre…"
        self._app_states = {a: "waiting" for a in self._selected}
        self.changed.emit()
        self._installer.start(self._selected)

    @Slot()
    def finish(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        DONE_MARKER.touch()
        # A telepített böngészők a tálcára kerülnek
        browsers = [a["id"] for a in catalog.CATEGORIES[0]["apps"]]
        desktop.pin_to_taskbar([a for a in self._installed if a in browsers])
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
        self._failures = [{"name": (catalog.find_app(a) or {}).get("name", a), "error": err}
                          for a, err in failed.items()]
        if not failed:
            self._summary = "Minden kész! A kiválasztott appok a Start menüben várnak."
        elif ok:
            self._summary = "Majdnem minden kész. Néhány appot nem sikerült telepíteni:"
        else:
            self._summary = "Sajnos most nem sikerült telepíteni az appokat:"
        self._progress = 100
        self._step = STEPS.index("done")
        self.changed.emit()
