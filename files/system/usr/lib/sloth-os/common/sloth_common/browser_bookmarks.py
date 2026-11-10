"""The bookmarks brought over from Windows, straight into the browsers installed on Sloth OS.

Moving over from Windows (windows_import) saves the bookmarks found there as a pending tree (save_pending()). They
go into every browser from the wizard that is installed as a Flatpak (apply_pending()), as one folder on the bookmarks
toolbar; each browser only once, and never while it is running. Nothing already there is changed or removed.

- Chromium-based browsers (Chrome, Brave, Edge, Vivaldi, Chromium, Opera): the profile's "Bookmarks" JSON file. Its
  "checksum" is left out: Chromium's reader (components/bookmarks/browser/bookmark_codec.cc) never checks it, and
  missing or repeated ids and guids are given new ones there. A browser that was never started gets the file in the
  profile folder it will use, so the bookmarks are there at its first start (Opera only after it, its layout differs).
- Firefox-based browsers (Firefox, LibreWolf, Zen, Floorp): the profile's places.sqlite, written the way Firefox
  itself writes a new bookmark (url_hash: toolkit/components/places/Helpers.cpp HashURL; moz_origins and
  foreign_count: the triggers in nsPlacesTriggers.h, which only exist inside Firefox). Firefox makes its profile at
  its first start (a profile made in advance is not used), so this happens at the next sign-in after that
  (/usr/libexec/sloth-os/bookmarks-import).
"""
import configparser
import json
import os
import secrets
import sqlite3
import subprocess
import time
from pathlib import Path

DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
PENDING = DATA / "sloth-os" / "windows-bookmarks.json"
APPS = Path.home() / ".var/app"
FLATPAK_DIRS = (Path("/var/lib/flatpak/app"), DATA / "flatpak/app")

# Flatpak id -> where its profiles are, inside ~/.var/app/<id>/ (the ones a browser that was never started gets)
CHROMIUM = {
    "com.google.Chrome": "config/google-chrome",
    "com.brave.Browser": "config/BraveSoftware/Brave-Browser",
    "com.microsoft.Edge": "config/microsoft-edge",
    "com.vivaldi.Vivaldi": "config/vivaldi",
    "org.chromium.Chromium": "config/chromium",
    "com.opera.Opera": None,     # no profile folder in advance: Opera keeps its files differently
}
FIREFOX = ("org.mozilla.firefox", "io.gitlab.librewolf-community", "app.zen_browser.zen", "one.ablaze.floorp")


# --- The pending tree ---------------------------------------------------------------------------------

def save_pending(folders, title):
    """folders: [{title, children: [{title, url} | {title, children}]}] -> into one folder called `title`."""
    if not count(folders):
        return
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    tmp = PENDING.with_suffix(".tmp")
    tmp.write_text(json.dumps({"title": title, "children": folders, "done": []}, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(PENDING)


def count(nodes):
    return sum(1 if "url" in n else count(n.get("children", [])) for n in nodes)


def _installed(app_id):
    return any((d / app_id).is_dir() for d in FLATPAK_DIRS)


def _running():
    try:
        out = subprocess.run(["flatpak", "ps", "--columns=application"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return set(out.split())


def apply_pending():
    """Into every installed browser that has not got them yet. -> the ids of the browsers done now."""
    try:
        data = json.loads(PENDING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    running = _running()
    if running is None:      # it can't be told which browser is open: rather not now
        return []
    folder = {"title": data.get("title") or "Windows", "children": data.get("children", [])}
    done = set(data.get("done", []))
    now = []
    for app_id in list(CHROMIUM) + list(FIREFOX):
        if app_id in done or app_id in running or not _installed(app_id):
            continue
        try:
            ok = _chromium(app_id, folder) if app_id in CHROMIUM else _firefox(app_id, folder)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            ok = False
        if ok:
            now.append(app_id)
    if now:
        data["done"] = sorted(done | set(now))
        tmp = PENDING.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PENDING)
    return now


# --- Chromium -----------------------------------------------------------------------------------------

def _chromium_profile(app_id):
    """The profile folder the browser uses (or will use), or None."""
    base = APPS / app_id
    states = [p for pattern in ("config/*/Local State", "config/*/*/Local State") for p in sorted(base.glob(pattern))]
    if states:
        user_data = states[0].parent
        try:
            last = json.loads(states[0].read_text(encoding="utf-8")).get("profile", {}).get("last_used")
        except (OSError, ValueError):
            last = None
        for name in (last, "Default"):
            if name and (user_data / name).is_dir():
                return user_data / name
        if (user_data / "Bookmarks").is_file() or app_id == "com.opera.Opera":
            return user_data      # Opera: the profile is the folder itself
        return user_data / "Default"
    if CHROMIUM.get(app_id):      # never started: the folder it will make
        return base / CHROMIUM[app_id] / "Default"
    return None


def _chromium_node(n, next_id, stamp):
    nid = next_id()
    if "url" in n:
        return {"id": str(nid), "type": "url", "name": n.get("title", ""), "url": n["url"], "date_added": stamp}
    return {"id": str(nid), "type": "folder", "name": n.get("title", ""), "date_added": stamp,
            "date_modified": stamp, "children": [_chromium_node(c, next_id, stamp) for c in n.get("children", [])]}


def _empty_root(nid, name):
    return {"id": str(nid), "type": "folder", "name": name, "children": [], "date_added": "0",
            "date_modified": "0"}


def _max_id(node):
    try:
        best = int(node.get("id", 0))
    except (TypeError, ValueError):
        best = 0
    return max([best] + [_max_id(c) for c in node.get("children", []) if isinstance(c, dict)])


def _chromium(app_id, folder):
    profile = _chromium_profile(app_id)
    if profile is None:
        return False
    path = profile / "Bookmarks"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        roots = data["roots"]
    else:
        roots = {"bookmark_bar": _empty_root(1, "Bookmarks bar"), "other": _empty_root(2, "Other bookmarks"),
                 "synced": _empty_root(3, "Mobile bookmarks")}
        data = {"roots": roots, "version": 1}
    last = [max(_max_id(r) for r in roots.values() if isinstance(r, dict))]

    def next_id():
        last[0] += 1
        return last[0]

    # Chromium's time: microseconds since 1601-01-01
    stamp = str(int((time.time() + 11644473600) * 1_000_000))
    roots["bookmark_bar"].setdefault("children", []).append(_chromium_node(folder, next_id, stamp))
    data.pop("checksum", None)
    profile.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("Bookmarks.sloth-tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=3), encoding="utf-8")
    tmp.replace(path)
    return True


# --- Firefox ------------------------------------------------------------------------------------------

def _places_hash(data):
    h = 0
    for b in data:
        h = (0x9E3779B9 * ((((h << 5) | (h >> 27)) & 0xFFFFFFFF) ^ b)) & 0xFFFFFFFF
    return h


def url_hash(url):
    """Firefox's moz_places.url_hash (HashURL in toolkit/components/places/Helpers.cpp)."""
    spec = url.encode("utf-8")
    full = _places_hash(spec[:1500])
    colon = spec[:50].find(b":")
    if colon < 0:
        return full
    return ((_places_hash(spec[:colon]) & 0xFFFF) << 32) + full


def _prefix_length(url):
    """getPrefixLength in SQLFunctions.cpp: up to and including ':', and '//' after it."""
    for i, ch in enumerate(url[:64]):
        if ch == ":":
            return i + 3 if url[i + 1:i + 3] == "//" else i + 1
    return 0


def _origin(url):
    """get_prefix() and get_host_and_port() of SQLFunctions.cpp."""
    start = _prefix_length(url)
    index, i = start, start
    while i < len(url) and url[i] not in "/?#":
        if url[i] == "@":
            index = i + 1
        i += 1
    return url[:start], url[index:i]


def _rev_host(host):
    """moz_places.rev_host: the host (without port) reversed, with a dot at the end ("gro.elpmaxe.")."""
    return host.rsplit(":", 1)[0].lower()[::-1] + "." if host else "."


GUID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _guid():
    return "".join(secrets.choice(GUID_CHARS) for _ in range(12))


def _firefox_profile(app_id):
    base = APPS / app_id
    if not base.is_dir():
        return None
    # ~/.mozilla/firefox, or since Firefox 147 ~/.config/mozilla/firefox (inside the sandbox); LibreWolf, Zen, Floorp
    # alike. The cache folder has a copy of the profile folders but no profiles.ini
    inis = [p for pattern in ("*/profiles.ini", "*/*/profiles.ini", "*/*/*/profiles.ini") for p in base.glob(pattern)]
    for ini in sorted(i for i in inis if "cache" not in str(i.relative_to(base)).lower()):
        root = ini.parent
        chosen = []
        installs = configparser.ConfigParser(interpolation=None)
        installs.read(root / "installs.ini", encoding="utf-8")
        chosen += [installs[s]["Default"] for s in installs.sections() if installs[s].get("Default")]
        profiles = configparser.ConfigParser(interpolation=None)
        profiles.read(ini, encoding="utf-8")
        chosen += [profiles[s]["Default"] for s in profiles.sections()
                   if s.startswith("Install") and profiles[s].get("Default")]
        chosen += [profiles[s]["Path"] for s in profiles.sections()
                   if s.startswith("Profile") and profiles[s].get("Default") == "1" and profiles[s].get("Path")]
        for rel in chosen:
            path = Path(rel) if Path(rel).is_absolute() else root / rel
            if (path / "places.sqlite").is_file():
                return path
    return None


def _firefox(app_id, folder):
    profile = _firefox_profile(app_id)
    if profile is None:
        return False
    # (its "lock" link stays after Firefox quits, with a process id from inside the sandbox: whether it runs is
    # told by flatpak ps in apply_pending())
    con = sqlite3.connect(profile / "places.sqlite", timeout=5)
    try:
        con.execute("BEGIN IMMEDIATE")
        toolbar = con.execute("SELECT id FROM moz_bookmarks WHERE guid = 'toolbar_____'").fetchone()
        if not toolbar:
            con.rollback()
            return False
        now = int(time.time() * 1_000_000)
        _firefox_add(con, toolbar[0], folder, now)
        con.execute("UPDATE moz_bookmarks SET lastModified = ? WHERE id = ?", (now, toolbar[0]))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return True


def _firefox_add(con, parent, node, now):
    position = con.execute("SELECT COUNT(*) FROM moz_bookmarks WHERE parent = ?", (parent,)).fetchone()[0]
    if "url" not in node:
        cur = con.execute("INSERT INTO moz_bookmarks (type, parent, position, title, dateAdded, lastModified, guid, "
                          "syncStatus, syncChangeCounter) VALUES (2, ?, ?, ?, ?, ?, ?, 1, 1)",
                          (parent, position, node.get("title", ""), now, now, _guid()))
        for child in node.get("children", []):
            _firefox_add(con, cur.lastrowid, child, now)
        return
    url = node["url"]
    if ":" not in url[:50]:
        return
    place = _firefox_place(con, url, node.get("title", ""))
    con.execute("INSERT INTO moz_bookmarks (type, fk, parent, position, title, dateAdded, lastModified, guid, "
                "syncStatus, syncChangeCounter) VALUES (1, ?, ?, ?, ?, ?, ?, ?, 1, 1)",
                (place, parent, position, node.get("title", ""), now, now, _guid()))
    # what moz_bookmarks_foreign_count_afterinsert_trigger does (place: queries are hidden, without frecency)
    query = url.startswith("place:")
    con.execute("UPDATE moz_places SET frecency = ? WHERE frecency = -1 AND id = ?", (0 if query else 1, place))
    con.execute("UPDATE moz_places SET foreign_count = foreign_count + 1, hidden = ?, recalc_frecency = ?, "
                "recalc_alt_frecency = ? WHERE id = ?", (int(query), int(not query), int(not query), place))


def _firefox_place(con, url, title):
    h = url_hash(url)
    row = con.execute("SELECT id FROM moz_places WHERE url_hash = ? AND url = ?", (h, url)).fetchone()
    if row:
        return row[0]
    prefix, host = _origin(url)
    # what moz_places_afterinsert_trigger does
    con.execute("INSERT INTO moz_origins (prefix, host, frecency, recalc_frecency, recalc_alt_frecency) "
                "VALUES (?, ?, -1, 1, 1) ON CONFLICT(host, prefix) DO UPDATE SET recalc_frecency = 1, "
                "recalc_alt_frecency = 1", (prefix, host))
    origin = con.execute("SELECT id FROM moz_origins WHERE prefix = ? AND host = ?", (prefix, host)).fetchone()[0]
    cur = con.execute("INSERT INTO moz_places (url, title, rev_host, hidden, frecency, guid, url_hash, origin_id) "
                      "VALUES (?, ?, ?, 0, -1, ?, ?, ?)", (url, title or None, _rev_host(host), _guid(), h, origin))
    return cur.lastrowid


if __name__ == "__main__":
    print(apply_pending())
