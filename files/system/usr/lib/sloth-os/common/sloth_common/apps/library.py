"""Az alkalmazások könyvtára: hol vannak a telepített programok, és mi tartozik hozzájuk.

Minden program saját, látható mappát kap a könyvtárban (alapból ~/Applications):

  ~/Applications/Battle.net/
    Program fájljai -> windows/drive_c/Program Files (x86)/Battle.net   (a telepített fájlok)
    windows/          a program saját Windows-környezete: C: meghajtó, beállítások, mentések
    .sloth/app.json   adatok: név, indítófájlok, futtató, bevált beállítások
    .sloth/icons/     ikonok a Start menühöz
    .directory        a mappa ikonja a Dolphinban

A háttérnapló a gyorsítótárba kerül (~/.cache/sloth-os/apps/<id>/naplo), mert bármikor törölhető.
A könyvtárak listája: ~/.config/sloth-os/applications.json ({"libraries": [...], "default": "..."}).
A Start menü bejegyzések az indítófájlt a Windows-környezethez képest tárolják, így a mappa
áthelyezhető (másik könyvtárba, másik meghajtóra), a bejegyzések érvényesek maradnak.

A régi hely (~/.local/share/sloth-os/windows-programs/<id>/, benne files/ és meta.json) is olvasható;
a migrate_legacy() egyszer áthozza a programokat az új helyre.
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
LOG_ROOT = CACHE_HOME / "sloth-os" / "apps"

SCHEMA = 1
# Egyedi .exe-k (nem telepítők) közös Windows-környezete
SHARED_ID = "egyeb-programok"
# A Proton a Windows-felhasználót így hívja
WIN_USER = "steamuser"
SNAPSHOT_NAME = "pillanatkep"
# Ezeken a fájlrendszereken működik a Windows-környezet (szimbolikus linkek, jogosultságok, kis-nagybetű)
SUPPORTED_FS = {"btrfs", "ext4", "ext3", "xfs", "f2fs", "bcachefs"}


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "program"


def folder_name(name):
    """A program neve mappanévként: "Battle.net" marad, a "/" és a vezető pont nem lehet benne."""
    s = re.sub(r"[/\\\x00-\x1f]+", "-", name or "").strip().lstrip(".").strip()
    return s[:80].strip() or "Program"


def _write_json(path, data):
    """Atomikus írás: félbeszakadt mentés után is ép marad a fájl."""
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


# --- Könyvtárak ------------------------------------------------------------------------------------

def libraries():
    """A beállított könyvtárak (az alapértelmezett mindig köztük van), sorrendben."""
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
    """Könyvtár felvétele (az itt lévő programok is látszanak); default: ide települnek az újak."""
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
    """Ide települnek az új programok (a meglévők maradnak, ahol vannak)."""
    add_library(path, default=True)


def filesystem(path):
    """A mappát tartalmazó fájlrendszer típusa (pl. "btrfs"), vagy "" ha nem derül ki."""
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(path)],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def supported_location(path):
    """Mehet-e ide Windows-program (NTFS-en, exFAT-on és FAT-on a Windows-környezet nem működik)."""
    fs = filesystem(path)
    return not fs or fs in SUPPORTED_FS


# --- Egy Windows-környezet és egy program ----------------------------------------------------------

class WinEnv:
    """Egy Windows-környezet (prefix): a C: meghajtó és a registry. Lehet egy Sloth-program saját
    környezete, vagy egy másik programé (Steam, Lutris, Bottles, ~/.wine), amit csak olvasunk."""

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
        # A Windows nem kis-nagybetű érzékeny: keressük meg a valódi elérési utat
        cur = base
        for part in [p for p in rel.split("/") if p]:
            nxt = cur / part
            if not nxt.exists() and cur.is_dir():
                match = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
                nxt = match or nxt
            cur = nxt
        return cur

    def host_to_windows(self, path):
        """<prefix>/drive_c/Program Files/X/x.exe -> C:\\Program Files\\X\\x.exe (ha a C: meghajtón van)."""
        try:
            rel = Path(path).relative_to(self.prefix / "drive_c")
        except ValueError:
            return None
        return "C:\\" + "\\".join(rel.parts)

    def list_exes(self):
        """Az összes .exe a Windows-környezetben (a Windows saját fájljai nélkül)."""
        drive_c = self.prefix / "drive_c"
        out = []
        users = drive_c / "users"
        tops = ["Program Files", "Program Files (x86)", "Games"]
        # a felhasználó saját programjai (a Protonnál „steamuser”, a sima Wine-nál a Linuxos név)
        if users.is_dir():
            tops += [f"users/{u.name}/AppData" for u in users.iterdir() if u.is_dir() and not u.is_symlink()]
        for top in tops:
            base = drive_c / top
            if base.is_dir():
                out += [p for p in base.rglob("*") if p.suffix.lower() == ".exe" and p.is_file()]
        return out


class App(WinEnv):
    """Egy telepített program a mappája alapján (a régi elrendezést is ismeri)."""

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
        # az azonosító nem változik (a Start menü bejegyzések erre hivatkoznak), a mappa neve igen
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
        """"windows": saját Windows-környezet; "steam": a Steamben van, a Steam indítja."""
        return self.meta.get("kind", "windows")

    @property
    def log_dir(self):
        return LOG_ROOT / self.id / "naplo"

    def link_files(self, install_dir, label):
        """Látható hivatkozás a telepített fájlokra a program mappájában (relatív, így áthelyezhető)."""
        if self.legacy or not install_dir:
            return
        link = self.dir / folder_name(label)
        try:
            target = os.path.relpath(install_dir, self.dir)
            for old in self.dir.iterdir():
                # a korábbi hivatkozás (más néven, pl. nyelvváltás után) ne maradjon ott
                if old.is_symlink() and old != link and os.readlink(old) == target:
                    old.unlink()
            if link.is_symlink():
                link.unlink()
            if not link.exists():
                link.symlink_to(target, target_is_directory=True)
        except OSError as e:
            log.warning("hivatkozás a fájlokra: %s", e)

    def set_folder_icon(self, icon):
        """A mappa ikonja a Dolphinban (.directory)."""
        if self.legacy or not icon:
            return
        try:
            (self.dir / ".directory").write_text(f"[Desktop Entry]\nIcon={icon}\n", encoding="utf-8")
        except OSError as e:
            log.warning("mappaikon: %s", e)

    def busy(self):
        return prefix_busy(self)


# --- Keresés -----------------------------------------------------------------------------------------

def _app_dirs():
    for lib in libraries():
        if lib.is_dir():
            for d in sorted(lib.iterdir(), key=lambda p: p.name.lower()):
                if (d / ".sloth" / "app.json").is_file():
                    yield d
    if LEGACY_ROOT.is_dir():
        for d in sorted(LEGACY_ROOT.iterdir()):
            if d.is_dir() and ((d / "meta.json").is_file() or (d / "files").is_dir()):
                yield d


def all_apps():
    """Minden telepített program (ugyanaz az azonosító csak egyszer: az új hely nyer)."""
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
    """Telepítettük-e már ezt a programot? -> App vagy None

    Egyezik, ha az azonosító a program nevéből jön (a régi, dupla telepítésnél „-2”, „-3”
    végződéssel), ugyanaz a neve, vagy ugyanazzal a telepítőfájllal telepítettük. Ha több is van,
    az nyer, amelyiknek van Start menü bejegyzése.
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


# --- Létrehozás, átnevezés, áthelyezés, eltávolítás -------------------------------------------------

def _free_folder(library, name):
    path = library / folder_name(name)
    n = 2
    while path.exists() or path.is_symlink():
        path = library / f"{folder_name(name)} ({n})"
        n += 1
    return path


def create(name, kind="windows", app_id=None, library=None, **meta):
    """Új program mappája a könyvtárban (az azonosító egyedi, a mappanév a program neve)."""
    library = Path(library or default_library())
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
    """Az egyedi .exe-k közös környezete (ha még nincs, létrejön)."""
    return find(SHARED_ID) or create(name, app_id=SHARED_ID)


def rename(app, new_name):
    """Új név és ehhez illő mappanév (ugyanabban a könyvtárban). -> az új App"""
    from . import menu

    app.save_meta(name=new_name)
    if app.legacy or folder_name(new_name) == app.dir.name:
        return app
    target = _free_folder(app.dir.parent, new_name)
    old_prefix = app.prefix
    try:
        app.dir.rename(target)
    except OSError as e:
        log.warning("átnevezés: %s", e)
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
    """A program áthelyezése egy másik könyvtárba. Azonos fájlrendszeren átnevezés (azonnali), különben
    másolás, ellenőrzés, és csak utána a régi törlése. -> az új App, vagy hibánál None (a régi érintetlen)."""
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
            log.warning("áthelyezés: %s", e)
            return None
    else:
        partial = target.with_name(f".{target.name}.masolas")
        try:
            if progress:
                progress("copy")
            subprocess.run(["cp", "-a", "--reflink=auto", str(app.dir), str(partial)], check=True,
                           capture_output=True)
            if _tree_size(partial) < _tree_size(app.dir):
                raise OSError("a másolat hiányos")
            partial.rename(target)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("áthelyezés: %s", e)
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
    """Biztonsági ellenőrzés: csak a könyvtárakban lévő, Sloth által kezelt mappát törlünk."""
    parent = app.dir.resolve().parent
    allowed = {p.resolve() for p in libraries()} | {LEGACY_ROOT.resolve()}
    managed = app.meta_path.is_file() or app.legacy
    return parent in allowed and managed and app.dir.is_dir() and not app.dir.is_symlink()


def remove(app):
    """A program Start menü bejegyzései, mappája és naplója. -> True, ha törölhető volt."""
    from . import menu

    if not removable(app):
        log.warning("nem törölhető: %s", app.dir)
        return False
    menu.remove_entries(app)
    shutil.rmtree(app.dir, ignore_errors=True)
    shutil.rmtree(LOG_ROOT / app.id, ignore_errors=True)
    return True


# --- Átköltözés a régi helyről -------------------------------------------------------------------

def migrate_legacy(busy=None):
    """A régi helyről (~/.local/share/sloth-os/windows-programs/) az új könyvtárba.

    Azonos fájlrendszeren átnevezés, így azonnali és nem foglal helyet. Ami fut (busy(app)), vagy más
    fájlrendszeren van, az marad (a régi hely is olvasható). Hibánál a program a régi helyén marad.
    -> az áthozott programok listája
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
            continue  # már áthoztuk (egy félbeszakadt átköltözés maradéka)
        name = meta.get("name") or app_id
        target = _free_folder(library, name)
        data = target / ".sloth"
        try:
            data.mkdir(parents=True)
            if old.prefix.is_dir():
                old.prefix.rename(target / "windows")
        except OSError as e:
            log.warning("átköltözés (%s): %s", app_id, e)
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
                child.rename(data / child.name)  # icons, pillanatkep és bármi más: semmi nem vész el
            except OSError as e:
                log.warning("átköltözés (%s/%s): %s", app_id, child.name, e)
        try:
            d.rmdir()
        except OSError:
            pass
        new = App(target)
        menu.relink(new, old.prefix)
        moved.append(new)
        log.info("átköltözve: %s -> %s", d, target)
    try:
        LEGACY_ROOT.rmdir()
    except OSError:
        pass
    return moved


def find_new(app_id):
    """Program az új könyvtárakban (a régi hely nélkül)."""
    return next((App(d) for d in _app_dirs() if not App(d).legacy and App(d).id == app_id), None)


# --- Fut-e a program --------------------------------------------------------------------------------

# A Wine saját háttérfolyamatai: a program kilépése után még pár másodpercig élhetnek
INFRA = {"services.exe", "winedevice.exe", "plugplay.exe", "explorer.exe", "rpcss.exe", "svchost.exe",
         "tabtip.exe", "conhost.exe", "start.exe", "steam.exe", "wineboot.exe", "rundll32.exe",
         "winemenubuilder.exe", "cmd.exe"}


def _windows_exe(proc):
    """A folyamat Windows-programjának neve (a Wine alatt az első paraméter a .exe útvonala), vagy None."""
    argv0 = (proc / "cmdline").read_bytes().split(b"\0", 1)[0].decode("utf-8", "replace")
    name = re.split(r"[\\/]", argv0)[-1].lower()
    return name if name.endswith(".exe") else None


def running_exes(app):
    """A program Windows-környezetében futó programok nevei (a Wine saját folyamatai nélkül)."""
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
    """Fut-e még valami a program mappájában (pl. az indító kilépett, de a kliens tovább fut)."""
    return bool(running_exes(app))
