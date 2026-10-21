"""Which program is this? Recognized programs start with the fixes that belong to them.

umu applies umu-protonfixes' fixes based on the GAMEID, and Proton its own fixes tied to the
Steam AppID (that is why many games run better from Steam). The program's name is read from the .exe's
version data (product name), and we look it up:
  1. in umu's database (local: it comes with the system, and sloth-windows-prepare updates it),
  2. if it is not there, in the Steam store (an exact name match is needed).
The result (also if we did not find it) is saved in the program's data, so we only search once.
"""
import csv
import json
import logging
import os
import re
import subprocess
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("sloth-exe.identify")

SYSTEM_DB = Path("/usr/share/sloth-os/umu-database.csv")
CACHE_DB = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "umu-database.csv"
STEAM_SEARCH = "https://store.steampowered.com/api/storesearch/?term={}&l=english&cc=US"
TIMEOUT_S = 4
# These names do not tell which program it is
GENERIC = {"", "launcher", "game", "setup", "installer", "bootstrapper", "unity", "unreal engine",
           "microsoft windows operating system", "client", "app", "application", "program", "main"}


def normalize(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[™®©]", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def version_strings(exe):
    """The .exe's version data: {"ProductName": …, "FileDescription": …} (icoutils: wrestool)."""
    try:
        blob = subprocess.run(["wrestool", "-x", "-t", "16", str(exe)], capture_output=True,
                              timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for key in ("ProductName", "FileDescription", "CompanyName"):
        marker = (key + "\0").encode("utf-16-le")
        pos = blob.find(marker)
        if pos < 0:
            continue
        pos += len(marker)
        pos += (4 - pos % 4) % 4  # the value starts on a 4-byte boundary
        while blob[pos:pos + 2] == b"\0\0" and pos < len(blob):
            pos += 2
        end = pos
        while end + 1 < len(blob) and blob[end:end + 2] != b"\0\0":
            end += 2
        value = blob[pos:end].decode("utf-16-le", "replace").strip()
        if value:
            out[key] = value
    return out


# Words to cut from the end of the name ("World of Warcraft Launcher" -> "World of Warcraft")
_SUFFIX = re.compile(r"[\s_\-]+(launcher|setup|installer|install|client|x64|x86|win64|win32|64[\s\-]?bit|"
                     r"v?\d+(?:[._]\d+)*)$", re.I)


def _trimmed(name):
    prev = None
    while name and name != prev:
        prev, name = name, _SUFFIX.sub("", name).strip()
    return name


def candidates(exe, display_name=""):
    """The program's possible names, starting with the most reliable."""
    info = version_strings(exe)
    names = []
    for n in (info.get("ProductName", ""), info.get("FileDescription", ""), display_name, Path(exe).stem):
        names += [n, _trimmed(n)]
    seen, out = set(), []
    for n in names:
        key = normalize(n)
        if key and key not in GENERIC and key not in seen:
            seen.add(key)
            out.append(n)
    return out


def _umu_db():
    path = CACHE_DB if CACHE_DB.is_file() else SYSTEM_DB
    titles, exes = {}, {}
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                umu_id = (row.get("UMU_ID") or "").strip()
                if not umu_id.startswith("umu-"):
                    continue
                titles.setdefault(normalize(row.get("TITLE", "")), umu_id)
                for acronym in (row.get("COMMON ACRONYM (Optional)") or "").split(","):
                    if acronym.strip():
                        titles.setdefault(normalize(acronym), umu_id)
                for exe in (row.get("EXE_STRINGS (Optional)") or "").split(","):
                    if exe.strip():
                        exes.setdefault(exe.strip().lower(), umu_id)
    except OSError:
        pass
    return titles, exes


def _steam_search(name):
    url = STEAM_SEARCH.format(urllib.parse.quote(name))
    req = urllib.request.Request(url, headers={"User-Agent": "SlothOS/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        items = json.loads(resp.read()).get("items", [])
    wanted = normalize(name)
    for item in items:
        if item.get("type", "app") == "app" and normalize(item.get("name", "")) == wanted:
            return f"umu-{item['id']}"
    return None


def identify(exe, display_name="", online=True):
    """-> (GAMEID or None, the recognized name). On a network error None, and we try again next time."""
    names = candidates(exe, display_name)
    titles, exes = _umu_db()
    if Path(exe).name.lower() in exes:
        return exes[Path(exe).name.lower()], names[0] if names else ""
    for n in names:
        if normalize(n) in titles:
            return titles[normalize(n)], n
    if online:
        for n in names[:2]:
            try:
                found = _steam_search(n)
            except (OSError, ValueError) as e:
                log.info("Steam search failed (%s): %s", n, e)
                return None, ""
            if found:
                return found, n
    return "", names[0] if names else ""
