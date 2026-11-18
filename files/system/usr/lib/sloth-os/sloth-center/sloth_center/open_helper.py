"""The "I can't open this file" helper: a file with no app for it offers the right app, installed with one click.

Nothing is preinstalled on Sloth OS, so on a new computer a photo, a PDF, a Word document or a video has no app to
open it, and KDE would only show a long "Open with" list. Our entry (org.slothos.open.desktop, written by
tools/gen_desktop_entries.py) is registered for those file types, with the lowest preference:

  - if any other app can open the file (installed since, or chosen by the user), it opens there at once, and this
    helper shows nothing (it is only a step in between);
  - otherwise a small window names the app that opens it (for a Word document: LibreOffice, "an office suite …"),
    and one button installs it from Flathub (the same installer as Sloth Welcome, with a progress bar) and opens the
    file in it;
  - for a file type it has no suggestion for, it offers Discover's search for apps that open that type.

Start: sloth-open <file>
"""
import logging
import os
import sys
from pathlib import Path

OWN_ID = "org.slothos.open.desktop"
FLATPAK_EXPORTS = (Path("/var/lib/flatpak/exports/share/applications"),
                   Path.home() / ".local/share/flatpak/exports/share/applications")
FLATPAK_APPS = (Path("/var/lib/flatpak/app"), Path.home() / ".local/share/flatpak/app")

N_ = lambda s: s  # noqa: E731  (marks a text for translation; translated where it is shown)

OFFICE = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword",
          "application/vnd.oasis.opendocument.text", "application/rtf", "text/rtf", "application/x-mswrite",
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel",
          "application/vnd.oasis.opendocument.spreadsheet", "text/csv",
          "application/vnd.openxmlformats-officedocument.presentationml.presentation",
          "application/vnd.ms-powerpoint", "application/vnd.oasis.opendocument.presentation",
          "application/vnd.oasis.opendocument.graphics", "application/vnd.visio", "application/vnd.ms-publisher")
IMAGES = ("image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff", "image/heif", "image/avif",
          "image/svg+xml", "image/x-adobe-dng", "image/x-canon-cr2", "image/x-nikon-nef", "image/x-sony-arw",
          "image/jxl", "image/x-icon")
MEDIA = ("video/mp4", "video/x-matroska", "video/webm", "video/x-msvideo", "video/quicktime", "video/mpeg",
         "video/x-ms-wmv", "video/x-flv", "video/3gpp", "audio/mpeg", "audio/flac", "audio/x-wav", "audio/ogg",
         "audio/mp4", "audio/aac", "audio/x-ms-wma", "audio/x-opus+ogg")

# (file types, Flathub app id, app name, what it is, an icon of the theme while the app is not installed)
SUGGESTIONS = (
    (OFFICE, "org.libreoffice.LibreOffice", "LibreOffice",
     N_("an office suite for documents, spreadsheets and presentations"), "applications-office"),
    (("application/pdf",), "org.kde.okular", "Okular", N_("a PDF and document viewer"), "application-pdf"),
    (("image/vnd.adobe.photoshop", "image/x-xcf"), "org.gimp.GIMP", "GIMP", N_("an image editor"),
     "applications-graphics"),
    (("application/x-krita",), "org.kde.krita", "Krita", N_("a painting program"), "applications-graphics"),
    (("application/illustrator", "image/x-eps"), "org.inkscape.Inkscape", "Inkscape",
     N_("a vector drawing program"), "applications-graphics"),
    (("application/x-blender",), "org.blender.Blender", "Blender", N_("a 3D modelling program"),
     "applications-graphics"),
    (IMAGES, "org.kde.gwenview", "Gwenview", N_("an image viewer"), "image-x-generic"),
    (MEDIA, "org.videolan.VLC", "VLC", N_("a video and music player"), "applications-multimedia"),
    (("application/epub+zip", "application/x-mobipocket-ebook", "application/x-fictionbook+xml"),
     "com.github.johnfactotum.Foliate", "Foliate", N_("an e-book reader"), "x-office-document"),
    (("application/x-bittorrent",), "org.qbittorrent.qBittorrent", "qBittorrent", N_("a torrent downloader"),
     "folder-download"),
    (("text/plain", "text/markdown", "text/x-log"), "org.kde.kwrite", "KWrite", N_("a text editor"),
     "accessories-text-editor"),
)
# the entry's name (in "Open with" lists; tools/gen_desktop_entries.py)
ENTRY_NAME = N_("Find an app for this file")
# every type above: the entry's MimeType list (tools/gen_desktop_entries.py)
ALL_TYPES = tuple(t for types, *_ in SUGGESTIONS for t in types)

log = logging.getLogger("sloth-open")


def content_type(path):
    from gi.repository import Gio
    try:
        info = Gio.File.new_for_path(str(path)).query_info("standard::content-type", Gio.FileQueryInfoFlags.NONE, None)
        return info.get_content_type() or ""
    except Exception:
        guess, _uncertain = Gio.content_type_guess(str(path), None)
        return guess or ""


def suggestion(mime):
    """(app id, name, what it is, icon) for a file type, or None."""
    for types, app_id, name, what, icon in SUGGESTIONS:
        if mime in types:
            return app_id, name, what, icon
    return None


def other_app(mime):
    """An app other than this helper that opens exactly this type (the default one first), or None.

    Only apps for the type itself ("recommended" in GIO: their own MimeType list, or an association the user made):
    a Word document is a zip archive underneath, and Ark, the archive manager, would also count through that parent
    type."""
    from gi.repository import Gio
    chosen = user_choices(mime)
    exact = [a for a in Gio.AppInfo.get_recommended_for_type(mime)
             if a.get_id() != OWN_ID and (not is_browser(a) or a.get_id() in chosen)]
    default = Gio.AppInfo.get_default_for_type(mime, False)
    if default is not None and any(a.get_id() == default.get_id() for a in exact):
        return default
    return exact[0] if exact else None


def is_browser(app):
    """A web browser lists photos, PDFs and videos too (Chrome on the HP opened a .jpg, 2026-11-18): it only shows
    them, so for these types it does not count, unless the user chose it (user_choices)."""
    categories = app.get_categories() if hasattr(app, "get_categories") else ""
    return "WebBrowser" in (categories or "").split(";")


def user_choices(mime):
    """The apps the user picked for a type ("Open with" → remember, the file's properties): the user's
    mimeapps.list, its [Default Applications] and [Added Associations]. -> set of desktop file ids"""
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mimeapps.list"
    found, section = set(), ""
    try:
        lines = config.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return found
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            section = line
        elif section in ("[Default Applications]", "[Added Associations]") and line.startswith(mime + "="):
            found.update(x for x in line.split("=", 1)[1].split(";") if x)
    return found


def flatpak_installed(app_id):
    return any((d / app_id).is_dir() for d in FLATPAK_APPS)


def app_entry(app_id, mime):
    """The installed Flatpak's Start menu entry that opens this type (LibreOffice has one per part: Writer, Calc…),
    otherwise its main entry. -> Gio.DesktopAppInfo or None"""
    from gi.repository import Gio
    candidates = []
    for d in FLATPAK_EXPORTS:
        candidates += sorted(d.glob(f"{app_id}*.desktop")) if d.is_dir() else []
    main = None
    for path in candidates:
        info = Gio.DesktopAppInfo.new_from_filename(str(path))
        if info is None:
            continue
        if mime in (info.get_supported_types() or []):
            return info
        if path.name == f"{app_id}.desktop":
            main = info
    return main


def open_with(info, path):
    from gi.repository import Gio
    try:
        return bool(info.launch([Gio.File.new_for_path(str(path))], None))
    except Exception as e:
        log.warning("%s: %s", info.get_id(), e)
        return False


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: sloth-open <file>", file=sys.stderr)
        return 2
    path = Path(args[0]).expanduser()
    if args[0].startswith("file://"):
        from gi.repository import Gio
        path = Path(Gio.File.new_for_uri(args[0]).get_path() or args[0])
    mime = content_type(path)
    app = other_app(mime) if mime else None
    if app is not None and open_with(app, path):
        return 0                                    # an app opens it: nothing to show
    found = suggestion(mime)
    if found and flatpak_installed(found[0]):     # installed, but it did not say it opens this type
        entry = app_entry(found[0], mime)
        if entry is not None and open_with(entry, path):
            return 0
    return _window(path, mime, found)


def _window(path, mime, found):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
    app = QApplication([sys.argv[0]])
    app.setApplicationName("sloth-open")
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.open")
    from .i18n import Translator, catalog
    from PySide6.QtCore import Qt
    if catalog.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setWindowIcon(QIcon.fromTheme("system-search"))
    controller = OpenController(path, mime, found)
    translator = Translator()          # kept alive here: QML only borrows it
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("L", translator)
    engine.rootContext().setContextProperty("helper", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "qml" / "OpenHelper.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


def _controller_class():
    from PySide6.QtCore import QObject, Property, Signal, Slot

    from .i18n import tr

    class Controller(QObject):
        changed = Signal()
        _status_sig = Signal(str, int)
        _done_sig = Signal(bool)

        def __init__(self, path, mime, found):
            super().__init__()
            self._path, self._mime, self._found = path, mime, found
            self._state = "offer" if found else "unknown"
            self._status, self._percent = "", -1
            self._status_sig.connect(self._on_status)
            self._done_sig.connect(self._on_done)

        @Property(str, notify=changed)
        def state(self):
            return self._state                       # offer | unknown | installing | failed

        @Property(str, constant=True)
        def fileName(self):
            return self._path.name

        @Property(str, constant=True)
        def typeName(self):
            from gi.repository import Gio
            return Gio.content_type_get_description(self._mime) if self._mime else ""

        @Property(str, constant=True)
        def appName(self):
            return self._found[1] if self._found else ""

        @Property(str, constant=True)
        def appWhat(self):
            return tr(self._found[2]) if self._found else ""

        @Property(str, constant=True)
        def appIcon(self):
            from PySide6.QtGui import QIcon
            if not self._found:
                return "system-search"
            return self._found[0] if QIcon.hasThemeIcon(self._found[0]) else self._found[3]

        @Property(str, notify=changed)
        def status(self):
            return self._status

        @Property(int, notify=changed)
        def percent(self):
            return self._percent

        @Slot()
        def install(self):
            if not self._found or self._state == "installing":
                return
            sys.path.insert(0, "/usr/lib/sloth-os/sloth-welcome")
            from sloth_welcome.installer import Installer
            self._state, self._status, self._percent = "installing", "", 0
            self.changed.emit()
            self._installer = Installer(lambda text, _details, overall: self._status_sig.emit(text, overall),
                                        lambda *_: None,
                                        lambda ok, _failed: self._done_sig.emit(self._found[0] in ok))
            # the helper's apps are not all in Sloth Welcome's catalog (Gwenview, Okular… are not): given here
            self._installer.start([self._found[0]], extra_apps=[{"id": self._found[0], "name": self._found[1]}])

        def _on_status(self, text, overall):
            self._status, self._percent = text, overall
            self.changed.emit()

        def _on_done(self, ok):
            if ok:
                entry = app_entry(self._found[0], self._mime)
                if entry is not None and open_with(entry, self._path):
                    from PySide6.QtWidgets import QApplication
                    QApplication.quit()
                    return
            self._state = "failed"
            self.changed.emit()

        @Slot()
        def searchDiscover(self):
            import subprocess
            try:
                subprocess.Popen(["plasma-discover", "--mime", self._mime], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                log.warning("Discover: %s", e)
            from PySide6.QtWidgets import QApplication
            QApplication.quit()

    return Controller


def OpenController(path, mime, found):  # noqa: N802  (the class is made when Qt is loaded)
    return _controller_class()(path, mime, found)


if __name__ == "__main__":
    sys.exit(main())
