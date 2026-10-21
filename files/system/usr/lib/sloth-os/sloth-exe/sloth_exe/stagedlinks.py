"""Program versions swapped with a link (EA app) under Wine 10.

The EA app puts its files into a versioned folder ("EA Desktop/13.809.0.6322/EA Desktop"), and asks for a symbolic
link in the old place ("EA Desktop/EA Desktop"); that is how it switches versions on install and on every update. In Wine
10.0 (UMU-Proton 10) CreateSymbolicLinkW is only a stub: it reports success but creates no link. So in the next step
the installer does not find its background service and rolls everything back (INST-14-1627); and the updates
get stuck. Wine has link support since 10.19, and Proton 11 will include it.

Until then we fill in: while the program runs, we watch (inotify) the parent of the versioned folders, and as soon as EA
renames the active folder, we put a Linux link in its place (Wine follows it). The service would start within the next
milliseconds, so we do not check now and then but act on the rename immediately (2026-10-20, tried on a real machine).
Before starting we also point it at the latest version (after an earlier update without watching).

In general, for any program (from_log_line): Wine 10 writes every such request into its log
("fixme:file:CreateSymbolicLinkW (L"<link>" L"<target>" <flags>): stub"), with the link's place and target. Reading
that line, the runner afterwards does what Wine skipped: inside the program's Windows environment, never overwriting an existing file.
"""
import ctypes
import logging
import os
import re
import select
import threading
from pathlib import Path

log = logging.getLogger("sloth-exe.stagedlinks")

# (the parent of the versioned folders inside drive_c, the active folder's name)
STAGED = [("Program Files/Electronic Arts/EA Desktop", "EA Desktop")]
# For these .exe files we watch even if the folder does not exist yet (the installer creates it)
EXE_NAMES = re.compile(r"^(eaappinstaller|eadesktop|ealauncher|eabackgroundservice)", re.I)

IN_CREATE, IN_DELETE, IN_MOVED_FROM, IN_MOVED_TO = 0x100, 0x200, 0x40, 0x80


def _bases(prefix):
    return [(Path(prefix) / "drive_c" / parent, name) for parent, name in STAGED]


def applies(prefix, exe):
    return bool(EXE_NAMES.match(Path(exe).name)) or any(base.is_dir() for base, _name in _bases(prefix))


def _version_key(name):
    return [int(p) if p.isdigit() else 0 for p in re.split(r"[.-]", name)]


def fix(prefix):
    """A link to the latest versioned folder in the active folder's place, if there is no real folder there. -> whether anything changed"""
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
                continue  # a real folder: the program arranged it itself, we do not touch it
            active.symlink_to(target)
            log.info("link added: %s -> %s", active, target)
            changed = True
        except OSError as e:
            log.warning("link: %s: %s", active, e)
    return changed


class Watcher:
    """Background thread: while it runs, it adds the link right after each rename (see above)."""

    def __init__(self, prefix):
        self._prefix = prefix
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="stagedlinks", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        """Stops; waits for the thread (at most one round, 50 ms), so it does not touch the folder afterwards."""
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
                # the folder is created during the install: until it exists, we check every 50 ms
                for base, _name in _bases(self._prefix):
                    if base not in watched and base.is_dir():
                        mask = IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO
                        if libc.inotify_add_watch(fd, str(base).encode(), mask) >= 0:
                            watched.add(base)
                            fix(self._prefix)
                ready, _w, _x = select.select([fd], [], [], 0.05)
                if ready:
                    try:
                        os.read(fd, 65536)  # the event's contents are not needed: anything changed, we look again
                    except BlockingIOError:
                        pass
                # immediately on an event, otherwise every 50 ms (in case an event is missed, e.g. before subscribing)
                fix(self._prefix)
        finally:
            os.close(fd)


# --- In general: from Wine's log -------------------------------------------------------------------

_STUB = re.compile(r'CreateSymbolicLinkW \(L"((?:[^"\\]|\\.)*)" L"((?:[^"\\]|\\.)*)" (\d+)\): stub')


def _unescape(s):
    """Wine's debugstr_w output: it puts a backslash before backslashes and quotes."""
    return re.sub(r"\\(.)", r"\1", s)


def _resolve_ci(base, parts):
    """A Windows (case-insensitive) path according to the existing folders; the parts that do not exist unchanged."""
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
    """"C:\\Program Files\\x" -> <prefix>/drive_c/Program Files/x; other drives by dosdevices; None if it cannot
    be understood."""
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
    """If the line is a skipped link request: creates the link (inside the program's environment). -> whether it worked"""
    m = _STUB.search(line)
    if not m:
        return False
    link_win, target_win = _unescape(m.group(1)), _unescape(m.group(2))
    link = _unix_path(prefix, link_win)
    drive_c = (Path(prefix) / "drive_c").resolve()
    if link is None:
        log.info("link: path cannot be parsed: %s", link_win)
        return False
    try:
        parent = link.parent.resolve()
        parent.relative_to(drive_c)
    except (OSError, ValueError):
        log.info("link: outside the environment, skipped: %s", link_win)
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
            return False  # a real file or folder: we do not touch it
        if not parent.is_dir():
            return False
        link.symlink_to(target)
        log.info("link added (Wine skipped it): %s -> %s", link, target)
        return True
    except OSError as e:
        log.warning("link: %s: %s", link, e)
        return False
