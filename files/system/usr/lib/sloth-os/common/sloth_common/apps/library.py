"""The application library: where the installed programs are, and what belongs to them.

Every program gets its own visible folder in the library (by default ~/Applications):

  ~/Applications/Battle.net/
    Program files -> windows/drive_c/Program Files (x86)/Battle.net   (the installed files)
    windows/          the program's own Windows environment: C: drive, settings, saves
    .sloth/app.json   data: name, start files, runner, settings that worked
    .sloth/icons/     icons for the Start menu
    .directory        the folder's icon in Dolphin

The background log goes to the cache (~/.cache/sloth-os/apps/<id>/naplo), because it can be deleted any time.
The list of libraries: ~/.config/sloth-os/applications.json ({"libraries": [...], "default": "..."}).
The Start menu entries store the start file relative to the Windows environment, so the folder
can be moved (to another library, another drive), and the entries stay valid.

Programs without files of their own (started from elsewhere, e.g. by Steam; Linux packages installed in a box)
have hidden data: ~/.local/share/sloth-os/apps/<id>/.sloth/app.json.
The old location (~/.local/share/sloth-os/windows-programs/<id>/, with files/ and meta.json) is readable too;
migrate_legacy() brings the programs over to the new location once.
"""
import json
import logging
import os
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path

log = logging.getLogger("sloth-os.apps")

HOME = Path.home()
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache"))

DEFAULT_LIBRARY = HOME / "Applications"
CONFIG = CONFIG_HOME / "sloth-os" / "applications.json"
LEGACY_ROOT = DATA_HOME / "sloth-os" / "windows-programs"
# Data of programs without files of their own (started from elsewhere, installed in a box): these must not leave
# an empty folder in the visible library
RECORDS = DATA_HOME / "sloth-os" / "apps"
# These kinds of programs do not go into the visible library
RECORD_KINDS = {"link", "box"}
LOG_ROOT = CACHE_HOME / "sloth-os" / "apps"

SCHEMA = 1
# The shared Windows environment of single .exe files (not installers)
SHARED_ID = "egyeb-programok"  # "other programs" in Hungarian; an ID stored on existing machines, it stays
# This is what Proton calls the Windows user
WIN_USER = "steamuser"
SNAPSHOT_NAME = "pillanatkep"
# The Windows environment works on these file systems (symbolic links, permissions, case)
SUPPORTED_FS = {"btrfs", "ext4", "ext3", "xfs", "f2fs", "bcachefs"}


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "program"


def folder_name(name):
    """The program's name as a folder name: "Battle.net" stays, "/" and a leading dot are not allowed."""
    s = re.sub(r"[/\\\x00-\x1f]+", "-", name or "").strip().lstrip(".").strip()
    return s[:80].strip() or "Program"


def _write_json(path, data):
    """Atomic write: the file stays intact even after an interrupted save."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# --- Libraries ------------------------------------------------------------------------------------

def libraries():
    """The configured libraries (the default is always among them), in order."""
    cfg = _read_json(CONFIG)
    out = [Path(p).expanduser() for p in cfg.get("libraries", []) if isinstance(p, str) and p]
    out.insert(0, default_library())
    if DEFAULT_LIBRARY not in out:
        out.append(DEFAULT_LIBRARY)
    return list(dict.fromkeys(out))


def default_library():
    p = _read_json(CONFIG).get("default")
    return Path(p).expanduser() if isinstance(p, str) and p else DEFAULT_LIBRARY


def add_library(path, default=False):
    """Adds a library (the programs in it show up too); default: new programs are installed here."""
    path = Path(path).expanduser()
    cfg = _read_json(CONFIG)
    libs = [p for p in cfg.get("libraries", []) if isinstance(p, str)]
    if str(path) not in libs:
        libs.append(str(path))
    cfg["libraries"] = libs
    if default:
        cfg["default"] = str(path)
    _write_json(CONFIG, cfg)


def set_default_library(path):
    """New programs are installed here (the existing ones stay where they are)."""
    add_library(path, default=True)


def filesystem(path):
    """The type of the file system containing the folder (e.g. "btrfs"), or "" if it cannot be determined."""
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(path)],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def supported_location(path):
    """Whether Windows programs can go here (on NTFS, exFAT and FAT the Windows environment does not work)."""
    fs = filesystem(path)
    return not fs or fs in SUPPORTED_FS


# Where other internal drives are mounted: the installer puts them under /var/mnt (/mnt points there),
# Dolphin under /run/media/<user>
MOUNT_ROOTS = ("/var/mnt/", "/mnt/", "/run/media/")


def _existing(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _drive_mounts():
    """Mounted internal drives with a file system Windows programs work on: [(target, label)].
    USB sticks and other removable drives are left out (a program there disappears when it is unplugged)."""
    try:
        out = json.loads(subprocess.run(["findmnt", "--json", "--real", "-o", "TARGET,SOURCE,FSTYPE,LABEL"],
                                        capture_output=True, text=True, timeout=5).stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found = []
    stack = list(out.get("filesystems", []))
    while stack:
        fs = stack.pop(0)
        stack.extend(fs.get("children") or [])
        target, source = fs.get("target") or "", (fs.get("source") or "").split("[", 1)[0]
        if not target.startswith(MOUNT_ROOTS) or fs.get("fstype") not in SUPPORTED_FS:
            continue
        try:
            hotplug = subprocess.run(["lsblk", "-s", "-n", "-o", "HOTPLUG", source], capture_output=True,
                                     text=True, timeout=5).stdout.split()
        except (OSError, subprocess.SubprocessError):
            hotplug = []
        if "1" in hotplug or not os.access(target, os.W_OK):
            continue
        found.append((target, fs.get("label") or Path(target).name))
    return found


def install_locations():
    """Where a new Windows program can go: one place per drive, the default first.
    [{"path", "label" ("" for the system disk), "free" (bytes), "default"}]. The installer and Dolphin mount
    the other drives; a drive without a library yet gets one (<drive>/Applications) when a program goes there."""
    default = default_library()
    candidates = [(p, "") for p in libraries()] + [(Path(t) / "Applications", label) for t, label in _drive_mounts()]
    out, devices = [], set()
    for path, label in candidates:
        try:
            st = os.statvfs(_existing(path))
            dev = _existing(path).stat().st_dev
        except OSError:
            continue
        if dev in devices or not supported_location(path):
            continue
        devices.add(dev)
        if not label and dev != _existing(HOME).stat().st_dev:
            label = path.parent.name if path.name == "Applications" else path.name
        out.append({"path": str(path), "label": label, "free": st.f_bavail * st.f_frsize,
                    "default": path == default})
    out.sort(key=lambda loc: not loc["default"])
    return out


# --- A Windows environment and a program ----------------------------------------------------------

class WinEnv:
    """A Windows environment (prefix): the C: drive and the registry. It can be a Sloth program's own
    environment, or another app's (Steam, Lutris, Bottles, ~/.wine), which we only read."""

    def __init__(self, prefix):
        self.prefix = Path(prefix)

    def exists(self):
        return (self.prefix / "drive_c").is_dir()

    def windows_to_host(self, win_path):
        """C:\\Program Files\\X\\x.exe -> <prefix>/drive_c/Program Files/X/x.exe"""
        m = re.match(r"^([a-zA-Z]):[\\/]*(.*)$", win_path or "")
        if not m:
            return None
        drive = m.group(1).lower()
        rel = m.group(2).replace("\\", "/")
        base = self.prefix / ("drive_c" if drive == "c" else f"dosdevices/{drive}:")
        # Windows is not case-sensitive: find the real path
        cur = base
        for part in [p for p in rel.split("/") if p]:
            nxt = cur / part
            if not nxt.exists() and cur.is_dir():
                match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
                nxt = match or nxt
            cur = nxt
        return cur

    def host_to_windows(self, path):
        """<prefix>/drive_c/Program Files/X/x.exe -> C:\\Program Files\\X\\x.exe (if it is on the C: drive)."""
        try:
            rel = Path(path).relative_to(self.prefix / "drive_c")
        except ValueError:
            return None
        return "C:\\" + "\\".join(rel.parts)

    def list_exes(self):
        """All .exe files in the Windows environment (without Windows' own files)."""
        drive_c = self.prefix / "drive_c"
        out = []
        users = drive_c / "users"
        tops = ["Program Files", "Program Files (x86)", "Games"]
        # the user's own programs (with Proton "steamuser", with plain Wine the Linux name)
        if users.is_dir():
            tops += [f"users/{u.name}/AppData" for u in users.iterdir() if u.is_dir() and not u.is_symlink()]
        for top in tops:
            base = drive_c / top
            if base.is_dir():
                out += [p for p in base.rglob("*") if p.suffix.lower() == ".exe" and p.is_file()]
        return out


class App(WinEnv):
    """An installed program, based on its folder (it knows the old layout too)."""

    def __init__(self, directory):
        self.dir = Path(directory)
        self.legacy = self.dir.parent == LEGACY_ROOT
        if self.legacy:
            self.prefix = self.dir / "files"
            self.data = self.dir
            self.meta_path = self.dir / "meta.json"
        else:
            self.prefix = self.dir / "windows"
            self.data = self.dir / ".sloth"
            self.meta_path = self.data / "app.json"
        self.icons = self.data / "icons"
        self.snapshot = self.data / SNAPSHOT_NAME
        # the ID does not change (the Start menu entries refer to it), the folder name does
        self.id = self.meta.get("id") or self.dir.name

    def __repr__(self):
        return f"App({str(self.dir)!r})"

    def __eq__(self, other):
        return isinstance(other, App) and other.dir == self.dir

    def __hash__(self):
        return hash(self.dir)

    @property
    def meta(self):
        return _read_json(self.meta_path)

    def save_meta(self, **kv):
        meta = self.meta
        meta.update(kv)
        _write_json(self.meta_path, meta)

    @property
    def name(self):
        return self.meta.get("name") or self.dir.name

    @property
    def kind(self):
        """"windows": its own Windows environment; "steam": it is in Steam, and Steam starts it."""
        return self.meta.get("kind", "windows")

    @property
    def log_dir(self):
        return LOG_ROOT / self.id / "naplo"

    def link_files(self, install_dir, label):
        """A visible link to the installed files in the program's folder (relative, so it can be moved)."""
        if self.legacy or not install_dir:
            return
        link = self.dir / folder_name(label)
        try:
            target = os.path.relpath(install_dir, self.dir)
            for old in self.dir.iterdir():
                # the earlier link (under another name, e.g. after a language change) must not stay there
                if old.is_symlink() and old != link and os.readlink(old) == target:
                    old.unlink()
            if link.is_symlink():
                link.unlink()
            if not link.exists():
                link.symlink_to(target, target_is_directory=True)
        except OSError as e:
            log.warning("link to the files: %s", e)

    def set_folder_icon(self, icon):
        """The folder's icon in Dolphin (.directory)."""
        if self.legacy or not icon:
            return
        try:
            (self.dir / ".directory").write_text(f"[Desktop Entry]\nIcon={icon}\n", encoding="utf-8")
        except OSError as e:
            log.warning("mappaikon: %s", e)

    def busy(self):
        return prefix_busy(self)


# --- Searching -----------------------------------------------------------------------------------------

def _app_dirs():
    for lib in libraries() + [RECORDS]:
        if lib.is_dir():
            for d in sorted(lib.iterdir(), key=lambda p: p.name.lower()):
                if (d / ".sloth" / "app.json").is_file():
                    yield d
    if LEGACY_ROOT.is_dir():
        for d in sorted(LEGACY_ROOT.iterdir()):
            if d.is_dir() and ((d / "meta.json").is_file() or (d / "files").is_dir()):
                yield d


def all_apps():
    """Every installed program (the same ID only once: the new location wins)."""
    seen, out = set(), []
    for d in _app_dirs():
        app = App(d)
        if app.id not in seen:
            seen.add(app.id)
            out.append(app)
    return out


def find(app_id):
    return next((a for a in all_apps() if a.id == app_id), None)


def find_installed(name, installer):
    """Have we installed this program already? -> App or None

    It matches if the ID comes from the program's name (with the old duplicate installs' "-2", "-3"
    ending), it has the same name, or it was installed with the same installer file. If there are several,
    the one with a Start menu entry wins.
    """
    from . import menu

    slug = slugify(name)
    found = []
    for app in all_apps():
        if app.id == SHARED_ID or app.kind != "windows" or not app.exists():
            continue
        meta = app.meta
        same_installer = Path(meta.get("installer", "")).name.lower() == Path(installer).name.lower()
        same_name = slugify(meta.get("name", "")) == slug
        if app.id == slug or re.fullmatch(re.escape(slug) + r"-\d+", app.id) or same_installer or same_name:
            found.append(app)
    return max(found, key=lambda a: (bool(menu.entries(a)), a.id == slug, not a.legacy), default=None)


# --- Creating, renaming, moving, removing -------------------------------------------------

def _free_folder(library, name):
    path = library / folder_name(name)
    n = 2
    while path.exists() or path.is_symlink():
        path = library / f"{folder_name(name)} ({n})"
        n += 1
    return path


def create(name, kind="windows", app_id=None, library=None, **meta):
    """A new program's folder in the library (the ID is unique, the folder name is the program's name)."""
    library = Path(library or (RECORDS if kind in RECORD_KINDS else default_library()))
    if library != RECORDS and library not in libraries():
        add_library(library)   # a new drive (install_locations): its programs show up from now on
    base = app_id or slugify(name)
    ids = {a.id for a in all_apps()}
    new_id, n = base, 2
    while new_id in ids:
        new_id = f"{base}-{n}"
        n += 1
    folder = _free_folder(library, name)
    _write_json(folder / ".sloth" / "app.json",
                {"schema": SCHEMA, "id": new_id, "name": name, "kind": kind, "created": int(time.time()), **meta})
    return App(folder)


def shared_app(name):
    """The shared environment of single .exe files (created if it does not exist yet)."""
    return find(SHARED_ID) or create(name, app_id=SHARED_ID)


def rename(app, new_name):
    """A new name and a matching folder name (in the same library). -> the new App"""
    from . import menu

    app.save_meta(name=new_name)
    if app.legacy or folder_name(new_name) == app.dir.name:
        return app
    target = _free_folder(app.dir.parent, new_name)
    old_prefix = app.prefix
    try:
        app.dir.rename(target)
    except OSError as e:
        log.warning("renaming: %s", e)
        return app
    new = App(target)
    menu.relink(new, old_prefix)
    return new


def _same_filesystem(a, b):
    try:
        b.mkdir(parents=True, exist_ok=True)
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def move(app, library, progress=None):
    """Moves the program to another library. On the same file system it is a rename (instant), otherwise
    copy, check, and only then delete the old one. -> the new App, or None on error (the old one untouched)."""
    from . import menu

    library = Path(library)
    if app.legacy or app.dir.parent == library:
        return app
    if not supported_location(library):
        return None
    add_library(library)
    target = _free_folder(library, app.dir.name)
    old_prefix = app.prefix
    if _same_filesystem(app.dir, library):
        try:
            app.dir.rename(target)
        except OSError as e:
            log.warning("moving: %s", e)
            return None
    else:
        partial = target.with_name(f".{target.name}.masolas")
        try:
            if progress:
                progress("copy")
            subprocess.run(["cp", "-a", "--reflink=auto", str(app.dir), str(partial)], check=True,
                           capture_output=True)
            if _tree_size(partial) < _tree_size(app.dir):
                raise OSError("the copy is incomplete")
            partial.rename(target)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("moving: %s", e)
            shutil.rmtree(partial, ignore_errors=True)
            return None
        shutil.rmtree(app.dir, ignore_errors=True)
    new = App(target)
    menu.relink(new, old_prefix)
    return new


def _tree_size(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def removable(app):
    """Safety check: we only delete a Sloth-managed folder inside the libraries."""
    parent = app.dir.resolve().parent
    allowed = {p.resolve() for p in libraries()} | {LEGACY_ROOT.resolve(), RECORDS.resolve()}
    managed = app.meta_path.is_file() or app.legacy
    return parent in allowed and managed and app.dir.is_dir() and not app.dir.is_symlink()


def remove(app):
    """The program's Start menu entries, folder and log. -> True if it could be deleted."""
    from . import menu

    if not removable(app):
        log.warning("cannot be deleted: %s", app.dir)
        return False
    menu.remove_entries(app)
    shutil.rmtree(app.dir, ignore_errors=True)
    shutil.rmtree(LOG_ROOT / app.id, ignore_errors=True)
    return True


# --- Migrating from the old location -------------------------------------------------------------------

def migrate_legacy(busy=None):
    """From the old location (~/.local/share/sloth-os/windows-programs/) to the new library.

    On the same file system it is a rename, so it is instant and takes no space. Anything running (busy(app)) or on
    another file system stays (the old location is readable too). On error the program stays in its old place.
    -> the list of programs brought over
    """
    from . import menu

    if not LEGACY_ROOT.is_dir():
        return []
    library = default_library()
    moved = []
    for d in sorted(LEGACY_ROOT.iterdir()):
        if not d.is_dir():
            continue
        old = App(d)
        if (busy or prefix_busy)(old) or not _same_filesystem(d, library):
            continue
        meta = old.meta
        app_id = d.name
        if find_new(app_id):
            continue  # already brought over (left over from an interrupted migration)
        name = meta.get("name") or app_id
        target = _free_folder(library, name)
        data = target / ".sloth"
        try:
            data.mkdir(parents=True)
            if old.prefix.is_dir():
                old.prefix.rename(target / "windows")
        except OSError as e:
            log.warning("migration (%s): %s", app_id, e)
            shutil.rmtree(target, ignore_errors=True)
            continue
        meta.update(schema=SCHEMA, id=app_id, name=name, kind="windows")
        _write_json(data / "app.json", meta)
        old.meta_path.unlink(missing_ok=True)
        for child in list(d.iterdir()):
            try:
                if child.name == "naplo":
                    dest = LOG_ROOT / app_id / "naplo"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        child.rename(dest)
                        continue
                if child.name.startswith((".regi-", ".reflink-")):
                    shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink()
                    continue
                child.rename(data / child.name)  # icons, pillanatkep and anything else: nothing is lost
            except OSError as e:
                log.warning("migration (%s/%s): %s", app_id, child.name, e)
        try:
            d.rmdir()
        except OSError:
            pass
        new = App(target)
        menu.relink(new, old.prefix)
        moved.append(new)
        log.info("migrated: %s -> %s", d, target)
    try:
        LEGACY_ROOT.rmdir()
    except OSError:
        pass
    return moved


def find_new(app_id):
    """Program in the new libraries (without the old location)."""
    return next((App(d) for d in _app_dirs() if not App(d).legacy and App(d).id == app_id), None)


# --- Fut-e a program --------------------------------------------------------------------------------

# Wine's own background processes: they may live a few more seconds after the program exits
INFRA = {"services.exe", "winedevice.exe", "plugplay.exe", "explorer.exe", "rpcss.exe", "svchost.exe",
         "tabtip.exe", "conhost.exe", "start.exe", "steam.exe", "wineboot.exe", "rundll32.exe",
         "winemenubuilder.exe", "cmd.exe"}


def _windows_exe(proc):
    """The Windows program behind a Wine process, or None.

    Proton/Wine may put the Windows executable later in argv (the first argument can be wine64 or a
    Proton helper), and Wine may expose its Windows process name through /proc/<pid>/comm instead.
    Looking only at argv[0] misses both cases and makes a live app look like a failed quick launch.
    """
    try:
        args = (proc / "cmdline").read_bytes().split(b"\0")
    except OSError:
        args = []
    # Later arguments are more likely to identify the Windows client than wrapper/helper executables.
    for raw in reversed(args):
        value = raw.decode("utf-8", "replace").strip().strip('"')
        name = re.split(r"[\\/]", value)[-1].lower()
        if name.endswith(".exe") and name not in INFRA:
            return name
    try:
        name = (proc / "comm").read_text(encoding="utf-8", errors="replace").strip().lower()
    except OSError:
        return None
    return name if name.endswith(".exe") and name not in INFRA else None


def running_exes(app):
    """The names of the programs running in the program's Windows environment (without Wine's own processes)."""
    marker = b"WINEPREFIX=" + str(app.prefix).encode() + b"\0"
    out = set()
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return out
    for proc in proc_root.iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if marker in (proc / "environ").read_bytes():
                name = _windows_exe(proc)
                if name and name not in INFRA:
                    out.add(name)
        except OSError:
            continue
    return out


def prefix_busy(app):
    """Whether anything still runs in the program's folder (e.g. the launcher exited, but the client keeps running)."""
    return bool(running_exes(app))
