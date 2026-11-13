"""KDE's settings pages inside Sloth Center: one settings app (Sloth Center → More settings).

KDE's pages (KCMs) are loaded into Sloth Center's own window by org.slothos.kcmhost, a small QML module built into
the image (files/scripts/kcmhost.sh, source: /usr/src/sloth-os/kcmhost in files/system). The list of pages and
their names in the user's language come from the pages themselves (KcmCatalog, in QML); the groups (Input & Output,
Appearance & Style…) from System Settings' own category files, translated by KDE.

open_page(page): every "More options in KDE…" button of Sloth Center goes through here. The page opens inside Sloth
Center; if that is not possible (the module is missing, or an older page that can't be embedded) it opens in its
own small window (kcmshell6). Never the old System Settings: `systemsettings` itself leads here
(/usr/libexec/sloth-os/systemsettings-wrapper).
"""
import configparser
import logging
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from .i18n import catalog

log = logging.getLogger(__name__)

HOST = Path("/usr/lib64/qt6/qml/org/slothos/kcmhost/libkcmhost.so")
KCMS = Path("/usr/lib64/qt6/plugins/plasma/kcms")
CATEGORIES = Path("/usr/share/systemsettings/categories")
# Never listed: System Settings' own start page (a hub of links to the other pages)
HIDDEN = {"kcm_landingpage"}
# Not in the list, because a Sloth Center page covers them and opens them with its own button (no setting twice in
# the app); a search still finds them. Page → where its button is:
COVERED = {
    "kcm_access",                     # Accessibility → More settings
    "kcm_users",                      # Account and security → users
    "kcm_app-permissions",            # Account and security → App permissions
    "kcm_screenlocker",               # Account and security → Screen lock → More screen lock settings
    "kcm_lookandfeel",                # Appearance → More appearance settings
    "kcm_colors",                     # Appearance → More color settings
    "kcm_bluetooth",                  # Drivers and hardware → Bluetooth → Pair a device
    "kcm_gamecontroller",             # Drivers and hardware → Controllers
    "kcm_kscreen",                    # Drivers and hardware → Displays
    "kcm_pulseaudio",                 # Drivers and hardware → Sound → More sound settings
    "kcm_printer_manager",            # Printers and scanners → Add by hand
    "kcm_powerdevilprofilesconfig",   # Power and battery → More settings
    "kcm_autostart",                  # Services → Programs that start when you sign in
    "kcm_updates",                    # Updates → More update settings
}
# Pages without a group of their own in their metadata: where System Settings shows them
GROUP_OF = {"kcm_about-distro": "system-administration"}

_instance = None


def embeddable(page):
    """True if `page` is a KDE page Sloth Center can show in its own window."""
    return HOST.exists() and ((KCMS / "systemsettings" / f"{page}.so").exists() or (KCMS / f"{page}.so").exists())


def _name(section, lang):
    """A .desktop entry's Name in `lang` (pt_BR, then pt), or the English one."""
    for key in (f"Name[{lang}]", f"Name[{lang.replace('-', '_')}]", f"Name[{lang.split('_')[0].split('-')[0]}]"):
        if section.get(key):
            return section[key]
    return section.get("Name", "")


def categories(lang=None, directory=CATEGORIES):
    """{id: {"name", "icon", "parent", "weight"}} from System Settings' category files."""
    lang = lang or catalog.language()
    out = {}
    for f in sorted(Path(directory).glob("*.desktop")):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        try:
            cp.read(f, encoding="utf-8")
            s = cp["Desktop Entry"]
        except (configparser.Error, KeyError, OSError) as e:
            log.warning("%s: %s", f, e)
            continue
        cid = s.get("X-KDE-System-Settings-Category", "")
        if not cid or cid == "rootcategory":
            continue
        try:
            weight = int(s.get("X-KDE-Weight", "100"))
        except ValueError:
            weight = 100
        out[cid] = {"name": _name(s, lang), "icon": s.get("Icon", ""),
                    "parent": s.get("X-KDE-System-Settings-Parent-Category", ""), "weight": weight}
    return out


def group(pages, cats):
    """KDE's pages in top-level groups, as in System Settings' sidebar:
    [{"id", "name", "icon", "pages": [page…]}], groups by their weight, pages by name. A page whose group is
    unknown goes to a last group "" (shown as Other). Pages a Sloth Center page covers get "covered": True."""
    def top(cid):
        seen = set()
        while cid in cats and cats[cid]["parent"] and cid not in seen:
            seen.add(cid)
            cid = cats[cid]["parent"]
        return cid if cid in cats else ""

    groups = {}
    for p in pages:
        if p.get("id") in HIDDEN:
            continue
        p["covered"] = p.get("id") in COVERED       # shown only when searching
        groups.setdefault(top(p.get("category") or GROUP_OF.get(p.get("id"), "")), []).append(p)
    out = []
    for gid, items in groups.items():
        c = cats.get(gid, {})
        out.append({"id": gid, "name": c.get("name", ""), "icon": c.get("icon", "preferences-other"),
                    "weight": c.get("weight", 1000),
                    "pages": sorted(items, key=lambda p: p.get("name", "").casefold())})
    return sorted(out, key=lambda g: (g["weight"], g["name"]))


def open_window(page, args=""):
    """The page in its own small window (kcmshell6): for older pages, or when embedding is not possible."""
    exe = shutil.which("kcmshell6")
    cmd = [exe, page] + (["--args", args] if args else []) if exe else \
        ["/usr/libexec/sloth-os/systemsettings.real" if os.path.exists("/usr/libexec/sloth-os/systemsettings.real")
         else "systemsettings", page]
    try:
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError as e:
        log.warning("%s: %s", cmd, e)
        return False


def open_page(page, args=""):
    """Opens a KDE settings page: inside Sloth Center if possible, otherwise in its own window."""
    if _instance is not None and embeddable(page):
        _instance.openRequested.emit(page, args)
        return True
    return open_window(page, args)


class KdeSettingsController(QObject):
    """QML: kde.available, kde.groups(pages), kde.open(page), kde.openWindow(page); openRequested → Main.qml."""
    openRequested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        global _instance
        _instance = self
        self._cats = None

    @Property(bool, constant=True)
    def available(self):
        return HOST.exists()

    @Slot("QVariantList", result="QVariantList")
    def groups(self, pages):
        if self._cats is None:
            self._cats = categories()
        return group([dict(p) for p in pages], self._cats)

    @Slot(str)
    def open(self, page):
        open_page(page)

    @Slot(str, str)
    def openWithArgs(self, page, args):
        open_page(page, args)

    @Slot(str)
    def openWindow(self, page):
        open_window(page)
