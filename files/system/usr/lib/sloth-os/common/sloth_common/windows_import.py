"""Moving over from Windows: bringing over the user folders (Desktop, Documents…) and the browser bookmarks.

The Windows partition is only mounted read-only (udisksctl, with the system's password prompt if needed), and nothing
is written to it. The files go into the matching Sloth OS folders (xdg-user-dir); whatever is already there with the
same size is skipped (so an interrupted copy can continue), and a different file with the same name gets a "(Windows)" suffix.
The bookmarks (Chrome, Edge, Firefox) go into an HTML file on the Desktop; any browser can import it.
The OneDrive folder is skipped: it can be reached through the Cloud storage card in Sloth Center.

Sloth Welcome (sloth_welcome) uses it; Sloth Center (Disks) opens Welcome with this step.
"""
import html
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

# The Windows folder's name -> the xdg-user-dir key
FOLDERS = {
    "desktop": ("Desktop", "DESKTOP"),
    "documents": ("Documents", "DOCUMENTS"),
    "downloads": ("Downloads", "DOWNLOAD"),
    "music": ("Music", "MUSIC"),
    "pictures": ("Pictures", "PICTURES"),
    "videos": ("Videos", "VIDEOS"),
}
SKIP_USERS = {"public", "default", "default user", "all users", "defaultapppool", "wdagutilityaccount"}
SKIP_FILES = {"desktop.ini", "thumbs.db"}
SKIP_SUFFIXES = (".lnk",)       # Windows shortcuts: they do not work on Linux
MIN_NTFS_BYTES = 10 * 1024**3   # a smaller NTFS partition (e.g. recovery) is not a Windows system
CHROMIUM_BROWSERS = {
    "Google Chrome": "AppData/Local/Google/Chrome/User Data",
    "Microsoft Edge": "AppData/Local/Microsoft/Edge/User Data",
}
FIREFOX_PROFILES = "AppData/Roaming/Mozilla/Firefox/Profiles"


# --- Partitions ---------------------------------------------------------------------------------------

def candidates():
    """The possible Windows partitions on the machine (without mounting): [{device, label, size, locked}]"""
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-o", "PATH,FSTYPE,LABEL,SIZE,TYPE"],
                             capture_output=True, text=True, timeout=20).stdout
        devices = json.loads(out or "{}").get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found, stack = [], list(devices)
    while stack:
        dev = stack.pop(0)
        stack.extend(dev.get("children") or [])
        fstype = (dev.get("fstype") or "").lower()
        if dev.get("type") != "part" or int(dev.get("size") or 0) < MIN_NTFS_BYTES:
            continue
        if fstype in ("ntfs", "ntfs3", "bitlocker"):
            found.append({"device": dev["path"], "label": dev.get("label") or "", "size": int(dev["size"]),
                          "locked": fstype == "bitlocker"})
    return found


def _mountpoint(device):
    out = subprocess.run(["findmnt", "-nro", "TARGET", "--source", device], capture_output=True, text=True).stdout
    return out.split("\n")[0].strip()


def mount(device):
    """A read-only mount. -> (mount point, whether we mounted it); on error (None, False)"""
    current = _mountpoint(device)
    if current:
        return current, False
    r = subprocess.run(["udisksctl", "mount", "-b", device, "-o", "ro"], capture_output=True, text=True, timeout=120)
    current = _mountpoint(device)
    return (current, True) if r.returncode == 0 and current else (None, False)


def unmount(device):
    subprocess.run(["udisksctl", "unmount", "-b", device], capture_output=True, timeout=60)


# --- Survey ------------------------------------------------------------------------------------------

def _size(path):
    total = 0
    for root, dirs, files in os.walk(path):  # symbolic links (NTFS junctions) are not followed
        for name in files:
            p = os.path.join(root, name)
            if name.lower() in SKIP_FILES or name.lower().endswith(SKIP_SUFFIXES) or os.path.islink(p):
                continue
            try:
                total += os.stat(p).st_size
            except OSError:
                pass
    return total


def users(mnt):
    """The Windows users and the sizes of their folders. -> [] if this is not a Windows partition"""
    root = Path(mnt)
    if not (root / "Windows" / "System32").is_dir() or not (root / "Users").is_dir():
        return []
    result = []
    for home in sorted((root / "Users").iterdir()):
        if home.name.lower() in SKIP_USERS or not home.is_dir() or home.is_symlink():
            continue
        folders = {key: _size(home / win) for key, (win, _xdg) in FOLDERS.items() if (home / win).is_dir()}
        if not any(folders.values()):
            continue
        result.append({"name": home.name, "home": str(home), "folders": folders,
                       "bookmarks": len(_bookmark_sources(home))})
    return result


# --- Copying -------------------------------------------------------------------------------------------

def target_dir(key):
    xdg = FOLDERS[key][1]
    try:
        out = subprocess.run(["xdg-user-dir", xdg], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    if out and out != str(Path.home()):
        return Path(out)
    return Path.home() / FOLDERS[key][0]


def _already_copied(dest, size):
    """Whether this file is already there: under the same name, or with a "(Windows)" suffix from an earlier copy."""
    if dest.exists() and dest.stat().st_size == size:
        return True
    return any(p.stat().st_size == size for p in dest.parent.glob(f"{_glob_escape(dest.stem)} (Windows*){_glob_escape(dest.suffix)}")
               if p.is_file())


def _glob_escape(text):
    return "".join(f"[{c}]" if c in "*?[" else c for c in text)


def _free_name(dest):
    if not dest.exists():
        return dest
    n = 1
    while True:
        cand = dest.with_name(f"{dest.stem} (Windows{'' if n == 1 else f' {n}'}){dest.suffix}")
        if not cand.exists():
            return cand
        n += 1


def copy(home, keys, on_progress=lambda done, total, name: None, cancelled=lambda: False):
    """Copies the chosen folders. -> {"copied": count, "skipped": count, "failed": [path], "bytes": bytes}

    Whatever is already there with the same size is skipped; a file with the same name but other contents gets a "(Windows)" suffix.
    """
    home = Path(home)
    plan = []
    for key in keys:
        src_root = home / FOLDERS[key][0]
        dest_root = target_dir(key)
        for root, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for name in files:
                src = Path(root, name)
                if name.lower() in SKIP_FILES or name.lower().endswith(SKIP_SUFFIXES) or src.is_symlink():
                    continue
                try:
                    plan.append((src, dest_root / src.relative_to(src_root), src.stat().st_size))
                except OSError:
                    pass
    total = sum(size for _s, _d, size in plan)
    done, stats = 0, {"copied": 0, "skipped": 0, "failed": [], "bytes": 0}
    last = 0.0
    for src, dest, size in plan:
        if cancelled():
            break
        try:
            if dest.parent.is_dir() and _already_copied(dest, size):
                stats["skipped"] += 1
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                target = _free_name(dest) if dest.exists() else dest
                tmp = target.with_name(f".{target.name}.sloth-part")
                shutil.copyfile(src, tmp)
                shutil.copystat(src, tmp)
                tmp.replace(target)
                stats["copied"] += 1
                stats["bytes"] += size
        except OSError:
            stats["failed"].append(str(src))
        done += size
        now = time.monotonic()
        if now - last > 0.2:
            on_progress(done, total, src.name)
            last = now
    on_progress(done, total, "")
    return stats


# --- Bookmarks ---------------------------------------------------------------------------------------

def _bookmark_sources(home):
    found = []
    for browser, base in CHROMIUM_BROWSERS.items():
        for f in sorted((home / base).glob("*/Bookmarks")):
            found.append((browser, "chromium", f))
    for f in sorted((home / FIREFOX_PROFILES).glob("*/places.sqlite")):
        found.append(("Firefox", "firefox", f))
    return found


def _chromium_tree(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    roots = data.get("roots", {})

    def node(n):
        if n.get("type") == "url":
            return {"title": n.get("name", ""), "url": n.get("url", "")}
        return {"title": n.get("name", ""), "children": [node(c) for c in n.get("children", [])]}

    return [node(roots[k]) for k in ("bookmark_bar", "other", "synced") if k in roots]


def _firefox_tree(path):
    # the browser may lock the file: we read from a copy
    with tempfile.TemporaryDirectory() as tmp:
        copy_path = Path(tmp) / "places.sqlite"
        shutil.copyfile(path, copy_path)
        con = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
        rows = con.execute("SELECT b.id, b.parent, b.type, b.title, p.url FROM moz_bookmarks b "
                           "LEFT JOIN moz_places p ON b.fk = p.id ORDER BY b.parent, b.position").fetchall()
        con.close()
    children = {}
    for bid, parent, kind, title, url in rows:
        children.setdefault(parent, []).append((bid, kind, title or "", url))

    def build(bid, title):
        items = []
        for cid, kind, ctitle, url in children.get(bid, []):
            if kind == 1 and url and not url.startswith("place:"):
                items.append({"title": ctitle, "url": url})
            elif kind == 2:
                items.append(build(cid, ctitle))
        return {"title": title, "children": items}

    # 1 = root; below it the menu, the toolbar and the other bookmarks' folders (with internal names)
    names = {"menu": "Bookmarks Menu", "toolbar": "Bookmarks Toolbar", "unfiled": "Other Bookmarks",
             "mobile": "Mobile Bookmarks"}
    return [build(cid, names.get(ctitle, ctitle)) for cid, kind, ctitle, _u in children.get(1, []) if kind == 2]


def _html(nodes, depth=1):
    pad = "    " * depth
    out = [f"{pad}<DL><p>"]
    for n in nodes:
        if "url" in n:
            out.append(f'{pad}    <DT><A HREF="{html.escape(n["url"], quote=True)}">{html.escape(n["title"])}</A>')
        elif n.get("children"):
            out.append(f"{pad}    <DT><H3>{html.escape(n['title'])}</H3>")
            out.extend(_html(n["children"], depth + 1))
    out.append(f"{pad}</DL><p>")
    return out


def export_bookmarks(home, dest):
    """The Windows browsers' bookmarks into one HTML file (Netscape format). -> the number of bookmarks"""
    folders = []
    for browser, kind, path in _bookmark_sources(Path(home)):
        try:
            tree = _chromium_tree(path) if kind == "chromium" else _firefox_tree(path)
        except (OSError, ValueError, sqlite3.Error):
            continue
        label = browser if len([s for s in _bookmark_sources(Path(home)) if s[0] == browser]) == 1 \
            else f"{browser} ({path.parent.name})"
        folders.append({"title": label, "children": tree})

    def count(nodes):
        return sum(1 if "url" in n else count(n.get("children", [])) for n in nodes)

    total = count(folders)
    if not total:
        return 0
    lines = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
             '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
             "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>"] + _html(folders, 0)
    dest = _free_name(Path(dest)) if Path(dest).exists() else Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return total
