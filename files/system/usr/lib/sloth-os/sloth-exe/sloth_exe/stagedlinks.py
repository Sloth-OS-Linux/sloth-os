"""Linkkel cserélt programverziók (EA app) Wine 10 alatt.

Az EA app egy verziós mappába teszi a fájljait ("EA Desktop/13.809.0.6322/EA Desktop"), és a régi helyére
("EA Desktop/EA Desktop") szimbolikus linket kér; telepítéskor és minden frissítéskor így cserél verziót. A Wine
10.0-ban (UMU-Proton 10) a CreateSymbolicLinkW csak csonk: sikert jelez, de nem hoz létre linket. A telepítő ezért
a következő lépésben nem találja a háttérszolgáltatását, és mindent visszavon (INST-14-1627); a frissítések pedig
elakadnak. A Wine 10.19 óta van linktámogatás, a Proton 11-ben benne lesz.

Addig mi pótoljuk: amíg a program fut, figyeljük (inotify) a verziós mappák szülőjét, és amint az EA átnevezi az
aktív mappát, Linuxos linket teszünk a helyére (a Wine követi). A szolgáltatás a következő ezredmásodpercekben már
indulna, ezért nem időnként nézünk rá, hanem az átnevezésre azonnal lépünk (2026-10-20, valódi gépen kipróbálva).
Indítás előtt is a legújabb verzióra igazítjuk (egy korábbi, figyelés nélküli frissítés után).

Általánosan, bármelyik programnál (from_log_line): a Wine 10 minden ilyen kérést kiír a naplójába
("fixme:file:CreateSymbolicLinkW (L"<link>" L"<cél>" <jelzők>): stub"), a link helyével és céljával. A futtató ezt a
sort olvasva utólag elvégzi, amit a Wine kihagyott: a program Windows-környezetén belül, meglévő fájlt nem felülírva.
"""
import ctypes
import logging
import os
import re
import select
import threading
from pathlib import Path

log = logging.getLogger("sloth-exe.stagedlinks")

# (a verziós mappák szülője a drive_c-n belül, az aktív mappa neve)
STAGED = [("Program Files/Electronic Arts/EA Desktop", "EA Desktop")]
# Ezeknél a .exe-knél figyelünk akkor is, ha a mappa még nincs meg (a telepítő hozza létre)
EXE_NAMES = re.compile(r"^(eaappinstaller|eadesktop|ealauncher|eabackgroundservice)", re.I)

IN_CREATE, IN_DELETE, IN_MOVED_FROM, IN_MOVED_TO = 0x100, 0x200, 0x40, 0x80


def _bases(prefix):
    return [(Path(prefix) / "drive_c" / parent, name) for parent, name in STAGED]


def applies(prefix, exe):
    return bool(EXE_NAMES.match(Path(exe).name)) or any(base.is_dir() for base, _name in _bases(prefix))


def _version_key(name):
    return [int(p) if p.isdigit() else 0 for p in re.split(r"[.-]", name)]


def fix(prefix):
    """Az aktív mappa helyén link a legújabb verziós mappára, ha ott nincs valódi mappa. -> volt-e változás"""
    changed = False
    for base, name in _bases(prefix):
        try:
            versions = [d for d in base.iterdir() if d.name[:1].isdigit() and (d / name).is_dir()]
        except OSError:
            continue
        if not versions:
            continue
        target = f"{max(versions, key=lambda d: _version_key(d.name)).name}/{name}"
        active = base / name
        try:
            if active.is_symlink():
                if os.readlink(active) == target:
                    continue
                active.unlink()
            elif active.exists():
                continue  # valódi mappa: a program maga rendezte, nem nyúlunk hozzá
            active.symlink_to(target)
            log.info("link pótolva: %s -> %s", active, target)
            changed = True
        except OSError as e:
            log.warning("link: %s: %s", active, e)
    return changed


class Watcher:
    """Háttérszál: amíg fut, az átnevezésekre azonnal pótolja a linket (lásd fent)."""

    def __init__(self, prefix):
        self._prefix = prefix
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="stagedlinks", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        """Leállítás; megvárja a szálat (legfeljebb egy kör, 50 ms), hogy utána már ne nyúljon a mappához."""
        self._stop.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def _run(self):
        try:
            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        except (OSError, AttributeError) as e:
            log.warning("inotify: %s", e)
            return
        if fd < 0:
            log.warning("inotify: %s", os.strerror(ctypes.get_errno()))
            return
        watched = set()
        try:
            while not self._stop.is_set():
                # a mappa a telepítés közben jön létre: amíg nincs, 50 ms-onként nézünk rá
                for base, _name in _bases(self._prefix):
                    if base not in watched and base.is_dir():
                        mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO
                        if libc.inotify_add_watch(fd, str(base).encode(), mask) >= 0:
                            watched.add(base)
                            fix(self._prefix)
                ready, _w, _x = select.select([fd], [], [], 0.05)
                if ready:
                    try:
                        os.read(fd, 65536)  # az esemény tartalma nem kell: bármi változott, újranézünk
                    except BlockingIOError:
                        pass
                # eseményre azonnal, egyébként 50 ms-onként (ha egy esemény elmaradna, pl. a feliratkozás előtt)
                fix(self._prefix)
        finally:
            os.close(fd)


# --- Általánosan: a Wine naplójából -------------------------------------------------------------------

_STUB = re.compile(r'CreateSymbolicLinkW \(L"((?:[^"\\]|\\.)*)" L"((?:[^"\\]|\\.)*)" (\d+)\): stub')


def _unescape(s):
    """A Wine debugstr_w kimenete: a visszaperjel és az idézőjel elé visszaperjelet tesz."""
    return re.sub(r"\\(.)", r"\1", s)


def _resolve_ci(base, parts):
    """Windowsos (kis-nagybetűre érzéketlen) út a meglévő mappák szerint; a nem létező részek változatlanul."""
    cur = base
    for i, part in enumerate(parts):
        exact = cur / part
        if exact.exists() or exact.is_symlink():
            cur = exact
            continue
        try:
            match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        except OSError:
            match = None
        if match is None:
            return cur.joinpath(*parts[i:])
        cur = match
    return cur


def _unix_path(prefix, win):
    """"C:\\Program Files\\x" -> <prefix>/drive_c/Program Files/x; más meghajtó a dosdevices szerint; None, ha nem
    érthető."""
    m = re.match(r"^(?:\\\\\?\\)?([A-Za-z]):\\(.*)$", win)
    if not m:
        return None
    letter, rest = m.group(1).lower(), m.group(2)
    root = Path(prefix) / "dosdevices" / f"{letter}:"
    if letter == "c" or not root.exists():
        root = Path(prefix) / "drive_c"
    parts = [p for p in rest.split("\\") if p and p != "."]
    if ".." in parts:
        return None
    return _resolve_ci(root, parts)


def from_log_line(prefix, line):
    """Ha a sor egy kihagyott linkkérés: a link létrehozása (a program környezetén belül). -> sikerült-e"""
    m = _STUB.search(line)
    if not m:
        return False
    link_win, target_win = _unescape(m.group(1)), _unescape(m.group(2))
    link = _unix_path(prefix, link_win)
    drive_c = (Path(prefix) / "drive_c").resolve()
    if link is None:
        log.info("link: nem értelmezhető út: %s", link_win)
        return False
    try:
        parent = link.parent.resolve()
        parent.relative_to(drive_c)
    except (OSError, ValueError):
        log.info("link: a környezeten kívül, kihagyva: %s", link_win)
        return False
    if re.match(r"^[A-Za-z]:\\", target_win):
        target = _unix_path(prefix, target_win)
        if target is None:
            return False
        target = str(target)
    else:
        parts = [p for p in target_win.split("\\") if p]
        target = str(_resolve_ci(link.parent, parts).relative_to(link.parent)) if parts else ""
    if not target:
        return False
    try:
        if link.is_symlink():
            if os.readlink(link) == target:
                return True
            link.unlink()
        elif link.exists():
            return False  # valódi fájl vagy mappa: nem nyúlunk hozzá
        if not parent.is_dir():
            return False
        link.symlink_to(target)
        log.info("link pótolva (a Wine kihagyta): %s -> %s", link, target)
        return True
    except OSError as e:
        log.warning("link: %s: %s", link, e)
        return False
