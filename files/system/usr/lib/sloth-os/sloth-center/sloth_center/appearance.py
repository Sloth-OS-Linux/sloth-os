"""Appearance: the color scheme and the taskbar layout, the same ones Sloth Welcome offers at the first start.

Whoever changes their mind later can switch here; the shared code (sloth_common.appearance) sets them the same
way as Welcome did.
"""
import logging
import subprocess

from PySide6.QtCore import QObject, Property, Signal, Slot

from sloth_common import appearance as shared

from .i18n import N_, tr

log = logging.getLogger("sloth-center.appearance")

SCHEME_NAMES = {
    "SlothSilverDark": N_("Silver (dark)"),
    "SlothSilverLight": N_("Silver (light)"),
    "SlothWhite": N_("Snow White"),
    "SlothBlack": N_("Midnight Black"),
    "SlothMist": N_("Mist Blue"),
    "SlothNight": N_("Night Blue"),
    "SlothSage": N_("Sage"),
}

LAYOUT_TEXTS = {
    "windows10": (N_("Windows 10"), N_("Start menu and icons on the left")),
    "windows11": (N_("Windows 11"), N_("Start menu and icons in the center")),
    "mac": (N_("macOS-like"), N_("Top bar, floating dock at the bottom")),
    "ubuntu": (N_("Ubuntu-like"), N_("Top bar, dock on the left")),
}


class AppearanceController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scheme = shared.current_color_scheme()
        self._layout = shared.current_layout()
        self._error = ""

    @Property("QVariantList", constant=True)
    def schemes(self):
        return [{**s, "name": tr(SCHEME_NAMES.get(s["id"], s["id"]))} for s in shared.COLOR_SCHEMES]

    @Property("QVariantList", constant=True)
    def layouts(self):
        return [{"id": kind, "name": tr(LAYOUT_TEXTS[kind][0]), "description": tr(LAYOUT_TEXTS[kind][1])}
                for kind in shared.LAYOUTS]

    @Property(str, notify=changed)
    def currentScheme(self):
        return self._scheme

    @Property(str, notify=changed)
    def currentLayout(self):
        return self._layout

    @Property(str, notify=changed)
    def errorText(self):
        return self._error

    @Slot(str)
    def setScheme(self, scheme_id):
        if scheme_id == self._scheme:
            return
        if shared.apply_color_scheme(scheme_id):
            self._scheme, self._error = scheme_id, ""
        else:
            self._error = tr("Couldn't change the colors. Please try again.")
        self.changed.emit()

    @Slot(str)
    def setLayout(self, kind):
        # the current one may be clicked too: it is built again (e.g. after an update improved the layout)
        if shared.apply_layout(kind):
            self._layout, self._error = kind, ""
        else:
            self._error = tr("Couldn't change the taskbar. Please try again.")
        self.changed.emit()

    @Slot()
    def openSystemSettings(self):
        """Everything else about the look (themes, icons, fonts): KDE's own settings."""
        try:
            subprocess.Popen(["systemsettings", "kcm_lookandfeel"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("System Settings: %s", e)
