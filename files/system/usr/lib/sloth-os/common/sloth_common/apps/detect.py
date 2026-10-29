"""Which program got installed, and which file starts it?

Before installing we record what is already in the program's Windows environment (baseline), and compare
afterwards. What we work from, in order of reliability:
  1. the registry's "Uninstall" entry: name, publisher, version, install location, and the icon (DisplayIcon),
     which is most often the program itself,
  2. the shortcuts (.lnk) the installer put into the Start menu and on the desktop,
  3. the new .exe files in the install location, scored (matching name, size, depth; updaters,
     crash reporters, uninstallers and runtime installers drop out).
If a recipe (recipes.py) knows the program, the .exe it suggests goes first, and the ones to skip drop out.
If none of them is certain, the user chooses (and can browse too).
"""
import fnmatch
import os
import re
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import recipes, winreg

# Where the shared shortcuts are; the users' ones (with Proton "steamuser", with plain Wine the Linux name)
# a shortcut_dirs()-ben
SHORTCUT_DIRS = [
    "drive_c/ProgramData/Microsoft/Windows/Start Menu",
    "drive_c/users/Public/Desktop",
]
# These do not start the program (in the shortcut's or the .exe's name; Hungarian words too, for Hungarian installers)
SKIP_WORDS = ("uninstall", "uninst", "eltávolít", "remove", "readme", "help", "manual",
              "website", "web site", "license", "changelog", "release notes")
# These .exe files are certainly not the program (helper processes, updaters, runtimes)
HELPER_EXE = re.compile(
    r"(?i)(unins\d*|uninstall|setup|install|update|updater|patcher|crash|report|helper|redist|vc_?redist|"
    r"vcredist|dxsetup|dxwebsetup|dotnet|ndp\d|oalinst|physx|directx|ue4prereq|prereq|cefsharp|"
    r"qtwebengineprocess|webhelper|subprocess|elevat|service|agent|notification|bugreport|sentry|"
    r"unitycrashhandler|easyanticheat_setup|battleye_setup)")
INSTALLER_WORDS = ("setup", "install", "installer", "telepito", "telepítő", "_inst")
# Runtimes: the installer may register these too, but they are not the programs
REDIST_NAMES = re.compile(
    r"(?i)(microsoft visual c\+\+|\.net (framework|runtime|desktop)|directx|wine (mono|gecko)|"
    r"webview2|physx|openal|vulkan run ?time|xna framework|windows sdk)")
# Wine's own sample programs (iexplore, wmplayer, wordpad…): in a new environment they are created while the installer
# runs, so they look like "new" .exe files, but they do not belong to the program (by the lowercase _rel() path)
WINE_BUILTIN = re.compile(
    r"^drive_c/(windows/|program files( \(x86\))?/(internet explorer|windows media player|windows nt|common files)/)")
# Shared runtimes an installer brings along: Microsoft Edge WebView2 (with its updater and the Edge it may install),
# a built-in browser for logins (Roblox Studio, 2026-10-29). Not the program, and not a Start menu entry
SHARED_RUNTIME = re.compile(
    r"^drive_c/program files( \(x86\))?/microsoft/(edge|edgeupdate|edgewebview|edgecore|temp)/")
# A versioned folder in the path (e.g. "13.809.0.6322", "app-1.0.9"): it may disappear after an update
VERSION_DIR = re.compile(r"[\\/][^\\/]*\d+\.\d+\.\d+[^\\/]*[\\/]")
# File times may be a little coarser than the clock: written this many seconds before the install started still counts
CTIME_SLACK_S = 2


# Installer builders leave their name in the .exe's stub (the part before the packed data)
INSTALLER_MARKS = (b"Nullsoft Install System", b"NullsoftInst", b"Inno Setup", b"InstallShield", b".wixburn",
                   b"WixBundle", b"Squirrel", b"InstallAware", b"Setup Factory", b"Advanced Installer")
# A version resource string: the UTF-16 key, its terminating zero, padding to 4 bytes, then the value
VERSION_FIELD = re.compile(rb"(?:F\0i\0l\0e\0D\0e\0s\0c\0r\0i\0p\0t\0i\0o\0n\0|"
                           rb"O\0r\0i\0g\0i\0n\0a\0l\0F\0i\0l\0e\0n\0a\0m\0e\0)\0\0(?:\0\0)?((?:[^\0]\0){1,80})")


def _installer_inside(path, limit=8 * 1024 * 1024):
    """Whether the .exe is an installer by its contents: a known installer builder, or "setup"/"install" in its
    version information (e.g. 7-Zip's 7z2605-x64.exe: "7-Zip Setup"), when the file name does not say so."""
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError:
        return False
    if data[:2] != b"MZ":
        return False
    if any(mark in data for mark in INSTALLER_MARKS):
        return True
    for m in VERSION_FIELD.finditer(data):
        value = m.group(1).decode("utf-16-le", "replace").lower()
        if any(w in value for w in INSTALLER_WORDS):
            return True
    return False


def looks_like_installer(path):
    p = Path(path)
    if p.suffix.lower() == ".msi":
        return True
    low = p.stem.lower()
    return any(w in low for w in INSTALLER_WORDS) or _installer_inside(p)


def display_name(path):
    """setup_firefox-123.exe -> "Firefox" (as human a name as possible)."""
    stem = Path(path).stem
    s = re.sub(r"(?i)(setup|installer|install|x64|x86|win64|win32|amd64|_inst|-?v?\d+(\.\d+)+)", " ", stem)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if not s:
        return stem
    return s.title() if s.islower() else s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


# --- Shortcuts ------------------------------------------------------------------------------------

def parse_lnk(path):
    """The target of a Windows shortcut (.lnk). We only read the local path (MS-SHLLINK)."""
    try:
        data = Path(path).read_bytes()
        if len(data) < 0x4C or data[:4] != b"\x4c\x00\x00\x00":
            return None
        flags = struct.unpack_from("<I", data, 0x14)[0]
        pos = 0x4C
        if flags & 0x01:  # HasLinkTargetIDList
            pos += 2 + struct.unpack_from("<H", data, pos)[0]
        if not flags & 0x02:  # HasLinkInfo
            return None
        info = pos
        header_size = struct.unpack_from("<I", data, info + 4)[0]
        local_off = struct.unpack_from("<I", data, info + 0x10)[0]
        if header_size >= 0x24:  # Unicode variant
            uoff = struct.unpack_from("<I", data, info + 0x1C)[0]
            end = data.index(b"\x00\x00", info + uoff)
            if (end - info - uoff) % 2:
                end += 1
            return data[info + uoff:end].decode("utf-16-le", "replace")
        end = data.index(b"\x00", info + local_off)
        return data[info + local_off:end].decode("cp1252", "replace")
    except (OSError, ValueError, struct.error):
        return None


def shortcut_dirs(env):
    dirs = list(SHORTCUT_DIRS)
    users = env.prefix / "drive_c/users"
    if users.is_dir():
        for u in sorted(users.iterdir()):
            if u.is_dir() and not u.is_symlink() and u.name != "Public":
                dirs += [f"drive_c/users/{u.name}/AppData/Roaming/Microsoft/Windows/Start Menu",
                         f"drive_c/users/{u.name}/Desktop"]
    return dirs


def find_shortcuts(app):
    """The shortcuts created by the installer: [(name, host_exe, path of the .lnk)]."""
    seen, out = set(), []
    for rel in shortcut_dirs(app):
        base = app.prefix / rel
        if not base.is_dir():
            continue
        for lnk in sorted(base.rglob("*.lnk")):
            name = lnk.stem
            if any(w in name.lower() for w in SKIP_WORDS):
                continue
            target = parse_lnk(lnk)
            host = app.windows_to_host(target) if target else None
            if not host or host.suffix.lower() != ".exe" or not host.is_file():
                continue
            if any(w in host.name.lower() for w in SKIP_WORDS):
                continue
            key = str(host).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((name, host, lnk))
    return out


# --- Recognition --------------------------------------------------------------------------------------

@dataclass
class Candidate:
    name: str
    path: Path
    score: int
    checked: bool = False


@dataclass
class Detection:
    name: str = ""            # the program's name (from the registry), if it turned out
    publisher: str = ""
    version: str = ""
    install_dir: Path | None = None
    uninstall_key: str = ""
    candidates: list = field(default_factory=list)  # Candidates, the most likely first

    @property
    def sure(self):
        """Whether there is a certain launcher (the user does not need to choose)."""
        return any(c.score >= 80 for c in self.candidates)


def not_program(rel):
    """Wine's own files and shared runtimes (rel: _rel()): never the installed program."""
    rel = rel.replace("\\", "/")
    return bool(WINE_BUILTIN.match(rel) or SHARED_RUNTIME.match(rel))


def _rel(app, path):
    """Relative to the environment (so it can be compared even after the folder is renamed)."""
    try:
        return str(Path(path).relative_to(app.prefix)).lower()
    except ValueError:
        return str(path).lower()


def baseline(app):
    """What is already in the Windows environment before installing (nothing in a new environment)."""
    return {
        "time": time.time(),
        "keys": set(winreg.uninstall_entries(app.prefix)),
        "exes": {_rel(app, p) for p in app.list_exes()},
        "links": {_rel(app, lnk) for _n, _h, lnk in find_shortcuts(app)},
    }


def _exe_score(path, install_dir, name):
    if HELPER_EXE.search(path.stem) or any(w in path.name.lower() for w in SKIP_WORDS):
        return -100
    score = 30
    stem, want = _norm(path.stem), _norm(name)
    if want and (stem == want or stem == want + "launcher" or want.startswith(stem) or stem.startswith(want)):
        score += 30
    if install_dir:
        try:
            score -= 8 * (len(path.relative_to(install_dir).parts) - 1)
        except ValueError:
            score -= 20
    try:
        score += min(10, path.stat().st_size // (2 * 1024 ** 2))  # a bigger .exe: more likely the program
    except OSError:
        pass
    return score


def installed_running(app, running, since):
    """The .exe files written by the install (since: when it started) that run now (running: lowercase .exe names).
    IrfanView's installer starts the program at its end, and the install screen waited until the user closed it
    (2026-10-26/27): with no shortcut it is not certain what got installed until Wine writes the registry to disk,
    which may be only when the environment stops. A reinstall writes the files again, so the change time (which an
    installer cannot set back, unlike the modification time) counts, not whether the file is new. A second-stage
    installer (in a temporary folder, or with an installer's name) and helpers do not count. Only the name is looked
    at: the contents check (looks_like_installer) can find an installer builder's name inside a big program."""
    out = set()
    if not running:
        return out
    for p in app.list_exes():
        name, stem, rel = p.name.lower(), p.stem.lower(), _rel(app, p).replace("\\", "/")
        if (name not in running or "/temp/" in rel or not_program(rel) or HELPER_EXE.search(stem)
                or any(w in stem for w in INSTALLER_WORDS)):
            continue
        try:
            if p.stat().st_ctime >= since - CTIME_SLACK_S:
                out.add(name)
        except OSError:
            continue
    return out


def _common_dir(paths, drive_c):
    """The shared folder of the installed .exe files under Program Files (or another top folder)."""
    common = None
    for p in paths:
        try:
            rel = p.parent.relative_to(drive_c).parts
        except ValueError:
            continue
        if common is None:
            common = list(rel)
            continue
        n = 0
        while n < min(len(common), len(rel)) and common[n].lower() == rel[n].lower():
            n += 1
        common = common[:n]
    # at least the program's own folder is needed (Program Files/X, Games/X, users/<name>/AppData/Local/X)
    if not common or len(common) < (5 if common[0].lower() == "users" else 2):
        return None
    return drive_c.joinpath(*common)


def _via_link(path):
    """Instead of a path through a versioned folder, the one through the link next to it, if there is one.

    The EA app puts its files under "EA Desktop\\13.809.0.6322\\EA Desktop", and "EA Desktop\\EA Desktop" is a
    link to the current version; after an update the old folder disappears, the link stays (the .exe handler adjusts too).
    rglob does not go into the linked folder, so the .exe files turn up on the versioned path.
    """
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if not re.search(r"\d+\.\d+\.\d+", part):
            continue
        base, rest = Path(*parts[:i]), parts[i + 1:]
        try:
            links = [p for p in base.iterdir() if p.is_symlink()]
        except OSError:
            return path
        for link in links:
            target = Path(os.readlink(link)).parts
            # the link points to the same subfolder of a (possibly other) version: <version>/<subfolder…>
            if len(target) >= 1 and re.search(r"\d+\.\d+\.\d+", target[0]) \
                    and tuple(target[1:]) == rest[:len(target) - 1]:
                alt = link.joinpath(*rest[len(target) - 1:])
                if alt.is_file():
                    return alt
        return path
    return path


def detect(app, before=None, fallback_name=""):
    """After installing: what got installed and what starts it. before: baseline() from before the install."""
    before = before or {"keys": set(), "exes": set(), "links": set()}
    out = Detection()
    drive_c = app.prefix / "drive_c"

    # 1. registry: the new entries (that are not runtimes)
    entries = {k: v for k, v in winreg.uninstall_entries(app.prefix).items()
               if k not in before["keys"] and v.get("displayname") and not v.get("systemcomponent")
               and not REDIST_NAMES.search(str(v.get("displayname")))}
    icon_exes = []
    for key, v in entries.items():
        host = app.windows_to_host(winreg.exe_from_icon(v.get("displayicon")) or "")
        location = app.windows_to_host(str(v.get("installlocation") or "").strip('"')) \
            if v.get("installlocation") else None
        valid_icon = (host is not None and host.is_file() and not HELPER_EXE.search(host.stem)
                      and not not_program(_rel(app, host)))
        if valid_icon:
            icon_exes.append((str(v["displayname"]), host))
        # the program is the entry that has a startable icon or an install location
        if not out.uninstall_key or (valid_icon and not out.install_dir):
            out.name = str(v["displayname"]).strip()
            out.publisher = str(v.get("publisher") or "").strip()
            out.version = str(v.get("displayversion") or "").strip()
            out.uninstall_key = key
            if location is not None and location.is_dir():
                out.install_dir = location
            elif valid_icon:
                out.install_dir = host.parent

    name = out.name or fallback_name
    found = {}

    def add(cand_name, path, score):
        if not_program(_rel(app, path)):
            return  # e.g. the Microsoft Edge shortcut the WebView2 installer puts down
        path = _via_link(path)
        key = str(path).lower()
        if key not in found or found[key].score < score:
            found[key] = Candidate(cand_name, path, score)

    # 2. shortcuts (only the new ones): this is what the vendor meant as the launcher; then the registry's icon
    for lnk_name, host, lnk in find_shortcuts(app):
        if _rel(app, lnk) not in before["links"]:
            add(lnk_name, host, 90)
    for reg_name, host in icon_exes:
        add(reg_name, host, 85)

    # 3. the new .exe files in the install location (or, if that is not known, in their shared folder)
    new_exes = [p for p in app.list_exes()
                if _rel(app, p) not in before["exes"] and not not_program(_rel(app, p))]
    if not out.install_dir:
        out.install_dir = _common_dir(new_exes, drive_c)
    for p in new_exes:
        score = _exe_score(p, out.install_dir, name)
        if score > 0:
            same = _norm(p.stem) in (_norm(name), _norm(name) + "launcher")
            add(name if same and name else display_name(p), p, min(score, 75))

    # recipes: the suggested launcher first, the unneeded helper programs out
    prefer, skip = recipes.preferences(app.prefix)
    for key, c in list(found.items()):
        exe_name = c.path.name.lower()
        if any(fnmatch.fnmatch(exe_name, p.lower()) for p in skip):
            del found[key]
        elif any(fnmatch.fnmatch(exe_name, p.lower()) for p in prefer):
            c.score = max(c.score, 95)

    # with equal scores the path without a versioned folder goes first (e.g. the EA app's "EA Desktop\EA Desktop" link
    # instead of "13.809.0.6322": that stays valid after the program updates), then the shallower one
    cands = sorted(found.values(), key=lambda c: (-c.score, bool(VERSION_DIR.search(str(c.path))),
                                                  len(c.path.parts)))
    names = set()
    for i, c in enumerate(cands):
        # the certain hits (shortcuts, registry) all, otherwise only the best one;
        # the same name only once (e.g. Battle.net's shortcut and the registry's icon)
        if (c.score >= 80 or i == 0) and _norm(c.name) not in names:
            c.checked = True
            names.add(_norm(c.name))
    out.candidates = cands[:20]
    return out


def launch_candidates(app):
    """For editing afterwards: every possible launcher (shortcuts, the registry, the .exe files)."""
    det = detect(app, fallback_name=app.name)
    seen = {str(c.path).lower() for c in det.candidates}
    rest = [Candidate(display_name(p), p, 0) for p in app.list_exes()
            if str(p).lower() not in seen and not any(w in p.name.lower() for w in SKIP_WORDS)
            and not not_program(_rel(app, p))]
    return det.candidates + rest[:30]
