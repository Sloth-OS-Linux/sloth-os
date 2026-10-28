"""Network folders: a NAS or a shared folder of another computer, kept in the side panel of the file manager (Disks
page).

The graphical equivalent of `mount -t cifs` and an fstab line, without administrator rights: the folder becomes a
place in KDE's side panel (~/.local/share/user-places.xbel, the list Dolphin and every file dialog shows), so it is
there after a restart too. KIO connects when it is opened, and its sign-in window has "Remember password" (kept in
the password store, KWallet): that is what keeps the connection over a restart. Programs that are not KDE's get
the files through kio-fuse as ordinary paths. The computers on the network that share folders are found with
Avahi (`avahi-browse`, the same as Dolphin's Network place).
"""
import logging
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.netfolders")

PLACES = Path.home() / ".local/share/user-places.xbel"
SCHEMES = ("smb", "nfs", "sftp", "webdav", "webdavs", "ftp")
EMPTY_PLACES = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel>
<xbel xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks" \
xmlns:kdepriv="http://www.kde.org/kdepriv" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">
</xbel>
"""


def parse_address(text):
    r"""What the user typed -> a URL, or "" if it names no computer. Windows' form (\\nas\photos), //nas/photos,
    nas/photos and smb://nas/photos all mean the same; another scheme (nfs://, sftp://) stays."""
    text = text.strip()
    if not text:
        return ""
    if "://" in text:
        scheme, rest = text.split("://", 1)
        scheme = scheme.lower()
        if scheme not in SCHEMES:
            return ""
    else:
        scheme, rest = "smb", text.replace("\\", "/").lstrip("/")
    host, _, path = rest.partition("/")
    if not host or any(c in host for c in " \t<>\"'"):
        return ""
    path = "/".join(quote(unquote(p)) for p in path.split("/") if p)
    return f"{scheme}://{host}/{path}" if path else f"{scheme}://{host}/"


def default_name(url):
    """The shared folder's own name (or the computer's): smb://nas/Photos -> "Photos"."""
    parts = urlsplit(url)
    path = [p for p in parts.path.split("/") if p]
    return unquote(path[-1]) if path else (parts.hostname or url)


def folders(path=PLACES):
    """The network places in the side panel: [{name, url}]."""
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return []
    out = []
    for bm in root.iter("bookmark"):
        url = bm.get("href", "")
        if url.split("://", 1)[0].lower() in SCHEMES:
            out.append({"name": bm.findtext("title") or default_name(url), "url": url})
    return out


def add(url, name, path=PLACES):
    """Adds a place to the end of the side panel (the same entry KDE writes). The rest of the file is left as it is:
    the entry goes in as text before </xbel>, so nothing else of KDE's is rewritten."""
    path = Path(path)
    if any(f["url"] == url for f in folders(path)):
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = EMPTY_PLACES   # KDE adds its own places (Home, Trash, …) to a file without a version
    entry = (f' <bookmark href="{escape(url, {chr(34): "&quot;"})}">\n'
             f"  <title>{escape(name or default_name(url))}</title>\n"
             "  <info>\n"
             '   <metadata owner="http://freedesktop.org">\n'
             '    <bookmark:icon name="folder-network"/>\n'
             "   </metadata>\n"
             '   <metadata owner="http://www.kde.org">\n'
             f"    <ID>{int(time.time())}/{len(folders(path))}</ID>\n"
             "   </metadata>\n"
             "  </info>\n"
             " </bookmark>\n")
    end = text.rfind("</xbel>")
    if end < 0:
        raise ValueError("not a places file")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".xbel.sloth-tmp")
    tmp.write_text(text[:end] + entry + text[end:], encoding="utf-8")
    tmp.replace(path)


def remove(url, path=PLACES):
    """Removes the place with this address from the side panel (the folder on the network is not touched)."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    attr = re.escape(escape(url, {'"': "&quot;"}))
    new = re.sub(rf'[ \t]*<bookmark href="{attr}">.*?</bookmark>[ \t]*\n?', "", text, flags=re.S)
    if new != text:
        tmp = path.with_suffix(".xbel.sloth-tmp")
        tmp.write_text(new, encoding="utf-8")
        tmp.replace(path)


def _unescape_avahi(text):
    r"""avahi-browse -p writes special characters as \DDD (decimal): "My\032NAS" -> "My NAS"."""
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m[1])), text)


def parse_avahi(output):
    """`avahi-browse -tpr _smb._tcp` -> [{name, url}], one per computer (IPv4 and IPv6 give it twice)."""
    found = {}
    for line in output.splitlines():
        f = line.split(";")
        if len(f) < 9 or f[0] != "=":
            continue
        name, host = _unescape_avahi(f[3]), f[6]
        if host and name not in found:
            found[name] = {"name": name, "url": f"smb://{host}/"}
    return sorted(found.values(), key=lambda s: s["name"].lower())


def discover():
    try:
        r = subprocess.run(["avahi-browse", "-tpr", "_smb._tcp"], capture_output=True, text=True, timeout=10)
        return parse_avahi(r.stdout)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("avahi-browse: %s", e)
        return []


class NetFoldersController(QObject):
    changed = Signal()
    _found_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folders = folders()
        self._found = []
        self._searching = False
        self._searched = False
        self._message = ""
        self._found_ready.connect(self._on_found)

    folders = Property("QVariantList", lambda self: list(self._folders), notify=changed)
    searching = Property(bool, lambda self: self._searching, notify=changed)
    searched = Property(bool, lambda self: self._searched, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)

    @Property("QVariantList", notify=changed)
    def found(self):
        """The computers found, without the ones already in the side panel."""
        added = {urlsplit(f["url"]).hostname for f in self._folders}
        return [s for s in self._found if urlsplit(s["url"]).hostname not in added]

    @Slot()
    def search(self):
        if self._searching:
            return
        self._searching = True
        self.changed.emit()
        threading.Thread(target=lambda: self._found_ready.emit(discover()), daemon=True).start()

    def _on_found(self, found):
        self._found, self._searching, self._searched = found, False, True
        self.changed.emit()

    @Slot(str, result=bool)
    def isValid(self, text):
        return parse_address(text) != ""

    @Slot(str, str, result=bool)
    def addFolder(self, text, name):
        """Adds it to the side panel and opens it: the first time KIO asks for the user name and password."""
        url = parse_address(text)
        if not url:
            self._message = tr("This isn't a network address. Example: {example}", example=r"\\NAS\Photos")
            self.changed.emit()
            return False
        try:
            add(url, name.strip())
        except (OSError, ValueError) as e:
            log.warning("places: %s", e)
            self._message = tr("Couldn't add the folder.")
            self.changed.emit()
            return False
        self._folders = folders()
        self._message = tr("Added. When it asks for your password, let it remember it: then it connects by itself next time too.")
        self.changed.emit()
        self.open(url)
        return True

    @Slot(str)
    def removeFolder(self, url):
        try:
            remove(url)
        except OSError as e:
            log.warning("places: %s", e)
        self._folders = folders()
        self._message = ""
        self.changed.emit()

    @Slot(str)
    def open(self, url):
        subprocess.Popen(["dolphin", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
