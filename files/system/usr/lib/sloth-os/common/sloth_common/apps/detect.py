"""Melyik program települt, és melyik fájllal indul?

Telepítés előtt feljegyezzük, mi van már a program Windows-környezetében (baseline), utána
összevetjük. Amiből dolgozunk, a megbízhatóság sorrendjében:
  1. a registry „Uninstall” bejegyzése: név, kiadó, verzió, telepítési hely, és az ikon (DisplayIcon),
     ami a legtöbbször maga a program,
  2. a telepítő által a Start menübe és az asztalra tett parancsikonok (.lnk),
  3. az új .exe fájlok a telepítési helyen, pontozva (név egyezése, méret, mélység; a frissítők,
     hibajelentők, eltávolítók és a futtatókörnyezetek telepítői kiesnek).
Ha egyik sem biztos, a felhasználó választ (és tallózhat is).
"""
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from . import winreg
from .library import WIN_USER

SHORTCUT_DIRS = [
    "drive_c/ProgramData/Microsoft/Windows/Start Menu",
    f"drive_c/users/{WIN_USER}/AppData/Roaming/Microsoft/Windows/Start Menu",
    f"drive_c/users/{WIN_USER}/Desktop",
    "drive_c/users/Public/Desktop",
]
# Ezek nem a program indítói (a parancsikon vagy a .exe nevében)
SKIP_WORDS = ("uninstall", "uninst", "eltávolít", "remove", "readme", "help", "manual",
              "website", "web site", "license", "changelog", "release notes")
# Ezek a .exe-k biztosan nem a program (segédfolyamatok, frissítők, futtatókörnyezetek)
HELPER_EXE = re.compile(
    r"(?i)(unins\d*|uninstall|setup|install|update|updater|patcher|crash|report|helper|redist|vc_?redist|"
    r"vcredist|dxsetup|dxwebsetup|dotnet|ndp\d|oalinst|physx|directx|ue4prereq|prereq|cefsharp|"
    r"qtwebengineprocess|webhelper|subprocess|elevat|service|agent|notification|bugreport|sentry|"
    r"unitycrashhandler|easyanticheat_setup|battleye_setup)")
INSTALLER_WORDS = ("setup", "install", "installer", "telepito", "telepítő", "_inst")
# Futtatókörnyezetek: a telepítő ezeket is bejegyezheti, de nem ezek a programok
REDIST_NAMES = re.compile(
    r"(?i)(microsoft visual c\+\+|\.net (framework|runtime|desktop)|directx|wine (mono|gecko)|"
    r"webview2|physx|openal|vulkan run ?time|xna framework|windows sdk)")


def looks_like_installer(path):
    p = Path(path)
    if p.suffix.lower() == ".msi":
        return True
    low = p.stem.lower()
    return any(w in low for w in INSTALLER_WORDS)


def display_name(path):
    """setup_firefox-123.exe -> "Firefox" (amennyire lehet, emberi név)."""
    stem = Path(path).stem
    s = re.sub(r"(?i)(setup|installer|install|x64|x86|win64|win32|amd64|_inst|-?v?\d+(\.\d+)+)", " ", stem)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if not s:
        return stem
    return s.title() if s.islower() else s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


# --- Parancsikonok ------------------------------------------------------------------------------------

def parse_lnk(path):
    """Windows parancsikon (.lnk) célja. Csak a helyi elérési utat olvassuk (MS-SHLLINK)."""
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
        if header_size >= 0x24:  # Unicode változat
            uoff = struct.unpack_from("<I", data, info + 0x1C)[0]
            end = data.index(b"\x00\x00", info + uoff)
            if (end - info - uoff) % 2:
                end += 1
            return data[info + uoff:end].decode("utf-16-le", "replace")
        end = data.index(b"\x00", info + local_off)
        return data[info + local_off:end].decode("cp1252", "replace")
    except (OSError, ValueError, struct.error):
        return None


def find_shortcuts(app):
    """A telepítő által létrehozott parancsikonok: [(név, host_exe, .lnk útja)]."""
    seen, out = set(), []
    for rel in SHORTCUT_DIRS:
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


# --- Felismerés --------------------------------------------------------------------------------------

@dataclass
class Candidate:
    name: str
    path: Path
    score: int
    checked: bool = False


@dataclass
class Detection:
    name: str = ""            # a program neve (a registryből), ha kiderült
    publisher: str = ""
    version: str = ""
    install_dir: Path | None = None
    uninstall_key: str = ""
    candidates: list = field(default_factory=list)  # Candidate-ek, a legvalószínűbb elöl

    @property
    def sure(self):
        """Van-e biztos indító (a felhasználónak nem kell választania)."""
        return any(c.score >= 80 for c in self.candidates)


def _rel(app, path):
    """A környezethez képest (így a mappa átnevezése után is összevethető)."""
    try:
        return str(Path(path).relative_to(app.prefix)).lower()
    except ValueError:
        return str(path).lower()


def baseline(app):
    """Mi van már a Windows-környezetben telepítés előtt (új környezetnél semmi)."""
    return {
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
        score += min(10, path.stat().st_size // (2 * 1024 ** 2))  # nagyobb .exe: inkább a program
    except OSError:
        pass
    return score


def _common_dir(paths, drive_c):
    """A telepített .exe-k közös mappája a Program Files (vagy más felső mappa) alatt."""
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
    # legalább a program saját mappája kell (Program Files/X, Games/X, users/<név>/AppData/Local/X)
    if not common or len(common) < (5 if common[0].lower() == "users" else 2):
        return None
    return drive_c.joinpath(*common)


def detect(app, before=None, fallback_name=""):
    """Telepítés után: mi települt és mivel indul. before: baseline() a telepítés előttről."""
    before = before or {"keys": set(), "exes": set(), "links": set()}
    out = Detection()
    drive_c = app.prefix / "drive_c"

    # 1. registry: az új (és nem futtatókörnyezet) bejegyzések
    entries = {k: v for k, v in winreg.uninstall_entries(app.prefix).items()
               if k not in before["keys"] and v.get("displayname") and not v.get("systemcomponent")
               and not REDIST_NAMES.search(str(v.get("displayname")))}
    icon_exes = []
    for key, v in entries.items():
        host = app.windows_to_host(winreg.exe_from_icon(v.get("displayicon")) or "")
        location = app.windows_to_host(str(v.get("installlocation") or "").strip('"')) \
            if v.get("installlocation") else None
        valid_icon = host is not None and host.is_file() and not HELPER_EXE.search(host.stem)
        if valid_icon:
            icon_exes.append((str(v["displayname"]), host))
        # a program az a bejegyzés, amelyiknek van indítható ikonja vagy telepítési helye
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
        key = str(path).lower()
        if key not in found or found[key].score < score:
            found[key] = Candidate(cand_name, path, score)

    # 2. parancsikonok (csak az újak): ezt szánta a gyártó indítónak; utána a registry ikonja
    for lnk_name, host, lnk in find_shortcuts(app):
        if _rel(app, lnk) not in before["links"]:
            add(lnk_name, host, 90)
    for reg_name, host in icon_exes:
        add(reg_name, host, 85)

    # 3. az új .exe-k a telepítési helyen (vagy, ha az nem ismert, a közös mappájukban)
    new_exes = [p for p in app.list_exes() if _rel(app, p) not in before["exes"]]
    if not out.install_dir:
        out.install_dir = _common_dir(new_exes, drive_c)
    for p in new_exes:
        score = _exe_score(p, out.install_dir, name)
        if score > 0:
            same = _norm(p.stem) in (_norm(name), _norm(name) + "launcher")
            add(name if same and name else display_name(p), p, min(score, 75))

    cands = sorted(found.values(), key=lambda c: -c.score)
    names = set()
    for i, c in enumerate(cands):
        # a biztos találatok (parancsikonok, registry) mind, különben csak a legjobb;
        # ugyanaz a név csak egyszer (pl. a Battle.net parancsikonja és a registry ikonja)
        if (c.score >= 80 or i == 0) and _norm(c.name) not in names:
            c.checked = True
            names.add(_norm(c.name))
    out.candidates = cands[:20]
    return out


def launch_candidates(app):
    """Utólagos szerkesztéshez: minden lehetséges indító (parancsikonok, a registry, a .exe-k)."""
    det = detect(app, fallback_name=app.name)
    seen = {str(c.path).lower() for c in det.candidates}
    rest = [Candidate(display_name(p), p, 0) for p in app.list_exes()
            if str(p).lower() not in seen and not any(w in p.name.lower() for w in SKIP_WORDS)]
    return det.candidates + rest[:30]
