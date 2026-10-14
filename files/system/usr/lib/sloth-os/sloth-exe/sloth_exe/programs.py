"""A telepített Windows-programok nyilvántartása.

Minden program a saját mappájában él (~/.local/share/sloth-os/windows-programs/<név>/),
benne a program fájljai és egy meta.json. A Start menü bejegyzések a szokásos helyre
kerülnek (~/.local/share/applications/sloth-win-*.desktop). A felhasználó ebből
semmit nem lát: csak a programot a Start menüben.
"""
import json
import os
import re
import shlex
import struct
import subprocess
import tempfile
import unicodedata
from pathlib import Path

HOME = Path.home()
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
ROOT = DATA_HOME / "sloth-os" / "windows-programs"
APPS_DIR = DATA_HOME / "applications"
# Egyedi .exe-k (nem telepítők) közös helye
SHARED = "egyeb-programok"

# A Proton a Windows-felhasználót így hívja; ide kerülnek a felhasználói parancsikonok
WIN_USER = "steamuser"
SHORTCUT_DIRS = [
    "drive_c/ProgramData/Microsoft/Windows/Start Menu",
    f"drive_c/users/{WIN_USER}/AppData/Roaming/Microsoft/Windows/Start Menu",
    f"drive_c/users/{WIN_USER}/Desktop",
    "drive_c/users/Public/Desktop",
]
SKIP_WORDS = ("uninstall", "uninst", "eltávolít", "remove", "readme", "help", "manual",
              "website", "web site", "license", "changelog", "release notes")
INSTALLER_WORDS = ("setup", "install", "installer", "telepito", "telepítő", "_inst")


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "program"


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
    s = re.sub(r"[_\-.]+", " ", s).strip()
    if not s:
        return stem
    return s.title() if s.islower() else s


class Program:
    def __init__(self, slug):
        self.slug = slug
        self.dir = ROOT / slug
        self.prefix = self.dir / "files"
        self.icons = self.dir / "icons"
        self.meta_path = self.dir / "meta.json"

    @property
    def meta(self):
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def save_meta(self, **kv):
        meta = self.meta
        meta.update(kv)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def exists(self):
        return (self.prefix / "drive_c").is_dir()

    def windows_to_host(self, win_path):
        """C:\\Program Files\\X\\x.exe -> <prefix>/drive_c/Program Files/X/x.exe"""
        m = re.match(r"^([a-zA-Z]):[\\/](.*)$", win_path)
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

    def list_exes(self):
        """Az összes .exe a program mappájában (a rendszerfájlok nélkül)."""
        drive_c = self.prefix / "drive_c"
        out = []
        for top in ("Program Files", "Program Files (x86)", f"users/{WIN_USER}/AppData", "Games"):
            base = drive_c / top
            if base.is_dir():
                out += [p for p in base.rglob("*") if p.suffix.lower() == ".exe"]
        return out


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


def find_shortcuts(program):
    """A telepítő által létrehozott parancsikonok: [(név, host_exe)]."""
    seen, out = set(), []
    for rel in SHORTCUT_DIRS:
        base = program.prefix / rel
        if not base.is_dir():
            continue
        for lnk in sorted(base.rglob("*.lnk")):
            name = lnk.stem
            if any(w in name.lower() for w in SKIP_WORDS):
                continue
            target = parse_lnk(lnk)
            host = program.windows_to_host(target) if target else None
            if not host or host.suffix.lower() != ".exe" or not host.exists():
                continue
            if any(w in host.name.lower() for w in SKIP_WORDS):
                continue
            key = str(host).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((name, host))
    return out


def extract_icon(exe, dest_png):
    """Ikon a .exe-ből (icoutils). Ha nem megy, None: az általános ikon marad."""
    dest_png = Path(dest_png)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ico = Path(tmp) / "icon.ico"
        try:
            with open(ico, "wb") as f:
                subprocess.run(["wrestool", "-x", "-t", "14", str(exe)], stdout=f,
                               stderr=subprocess.DEVNULL, timeout=20, check=True)
            if ico.stat().st_size == 0:
                return None
            subprocess.run(["icotool", "-x", "-o", tmp, str(ico)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        pngs = list(Path(tmp).glob("*.png"))
        if not pngs:
            return None

        def size(p):  # icon_1_256x256x32.png -> 256*32
            m = re.search(r"_(\d+)x(\d+)x(\d+)\.png$", p.name)
            return int(m.group(1)) * 100 + int(m.group(3)) if m else 0

        best = max(pngs, key=size)
        dest_png.write_bytes(best.read_bytes())
        return dest_png


def desktop_file_path(program, exe):
    key = slugify(Path(exe).stem)
    return APPS_DIR / f"sloth-win-{program.slug}-{key}.desktop"


def add_to_menu(program, name, exe):
    """Start menü bejegyzés a programhoz. Az indítást mindig a Sloth .exe kezelő végzi."""
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    icon = extract_icon(exe, program.icons / f"{slugify(Path(exe).stem)}.png")
    path = desktop_file_path(program, exe)
    rel = os.path.relpath(exe, program.prefix)
    exec_line = " ".join(shlex.quote(a) for a in ["sloth-exe", "--launch", program.slug, rel])
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={exec_line}\n"
        f"Icon={icon or 'application-x-ms-dos-executable'}\n"
        "Terminal=false\n"
        "Categories=Game;X-SlothWindowsProgram;\n"
        "StartupNotify=true\n"
        f"X-Sloth-Program={program.slug}\n",
        encoding="utf-8")
    path.chmod(0o755)
    return path
