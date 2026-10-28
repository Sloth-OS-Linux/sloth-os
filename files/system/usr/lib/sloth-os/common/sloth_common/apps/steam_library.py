"""Moving a Steam game to another drive (Sloth Center → Games), the way Steam's own storage manager does it.

A Steam library is a folder with steamapps/ and a libraryfolder.vdf; the main one (Steam's own folder) lists every
library in steamapps/libraryfolders.vdf, with the games each one holds. A game is its manifest
(appmanifest_<appid>.acf) and its folders: the files (common/<installdir>), the Proton environment
(compatdata/<appid>, part of the saves and settings), the shader cache and the workshop content.
Steam must be closed: it rewrites libraryfolders.vdf when it exits.

On the same file system the folders are renamed (instant); otherwise they are copied, checked, and only then is
the old copy deleted, so an interruption leaves the game where it was. The Flatpak Steam is given access to the
new library's drive (a user override, no administrator approval).
"""
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path

from . import library, steam
from .steam import ci, vdf_dump, vdf_load

log = logging.getLogger("sloth-os.apps")

FLATPAK_ID = "com.valvesoftware.Steam"
# The folder Steam itself makes on another drive
LIBRARY_NAME = "SteamLibrary"
# Kept free on the target drive besides the game
SPARE_BYTES = 1024 ** 3
PARTIAL = ".sloth-moving"


def _read_vdf(path):
    try:
        return vdf_load(Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def _write_vdf(path, data):
    """Atomic: Steam never finds a half-written file. The first original is kept as .sloth-backup."""
    path = Path(path)
    backup = path.with_name(path.name + ".sloth-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(vdf_dump(data) + "\n", encoding="utf-8")
    tmp.replace(path)


def _same(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def find_game(root, appid):
    """Where a game is: {"library", "manifest", "installdir", "name", "size"} or None."""
    for lib in steam.library_folders(root):
        manifest = Path(lib) / "steamapps" / f"appmanifest_{appid}.acf"
        if not manifest.is_file():
            continue
        state = ci(_read_vdf(manifest), "AppState") or {}
        installdir = ci(state, "installdir")
        if not installdir or "/" in installdir or installdir in (".", ".."):
            return None
        try:
            size = int(ci(state, "SizeOnDisk") or 0)
        except ValueError:
            size = 0
        return {"library": Path(lib), "manifest": manifest, "installdir": installdir,
                "name": ci(state, "name") or "", "size": size}
    return None


def _parts(appid, installdir):
    """The game's folders and files besides the manifest, relative to the library."""
    return [f"steamapps/common/{installdir}", f"steamapps/compatdata/{appid}", f"steamapps/shadercache/{appid}",
            f"steamapps/workshop/content/{appid}", f"steamapps/workshop/appworkshop_{appid}.acf"]


def targets(root):
    """Where a game can go: Steam's own library, the libraries Steam already has, and a SteamLibrary folder on every
    other internal drive with a Linux file system (USB sticks are left out). [{"path", "label", "free"}]"""
    candidates = [(Path(root), "")] + [(Path(p), "") for p in steam.library_folders(root)[1:]]
    candidates += [(Path(t) / LIBRARY_NAME, label) for t, label in library._drive_mounts()]
    out, devices = [], set()
    for path, label in candidates:
        existing = library._existing(path)
        try:
            dev = existing.stat().st_dev
            free = shutil.disk_usage(existing).free
        except OSError:
            continue
        if dev in devices or not library.supported_location(path):
            continue
        devices.add(dev)
        out.append({"path": str(path), "label": label or ("" if _same(path, root) else path.parent.name), "free": free})
    return out


def ensure_library(root, lib):
    """Makes lib a Steam library and lists it in Steam's libraryfolders.vdf (once)."""
    lib = Path(lib)
    (lib / "steamapps").mkdir(parents=True, exist_ok=True)
    marker = lib / "libraryfolder.vdf"
    info = ci(_read_vdf(marker), "libraryfolder") or {}
    contentid = ci(info, "contentid")
    if not contentid:
        contentid = str(random.getrandbits(62))
        _write_vdf(marker, {"libraryfolder": {"contentid": contentid, "label": ""}})
    lf = Path(root) / "steamapps" / "libraryfolders.vdf"
    data = _read_vdf(lf) or {"libraryfolders": {}}
    folders = ci(data, "libraryfolders")
    if not isinstance(folders, dict):
        folders = data["libraryfolders"] = {}
    if any(_same(ci(v, "path") or "", lib) for v in folders.values() if isinstance(v, dict)):
        return
    index = str(max([int(k) for k in folders if k.isdigit()], default=-1) + 1)
    folders[index] = {"path": str(lib), "label": "", "contentid": contentid, "totalsize": "0",
                      "update_clean_bytes_tally": "0", "time_last_update_verified": "0", "apps": {}}
    _write_vdf(lf, data)


def grant_access(lib, flatpak):
    """The Flatpak Steam sees only its own folder: the new library's folder is added to what it may use."""
    if not flatpak:
        return True
    try:
        r = subprocess.run(["flatpak", "override", "--user", f"--filesystem={Path(lib)}", FLATPAK_ID],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("flatpak override: %s", e)
        return False
    return r.returncode == 0


def _set_app_library(root, appid, old_lib, new_lib, size):
    """libraryfolders.vdf: the game is listed under its new library."""
    lf = Path(root) / "steamapps" / "libraryfolders.vdf"
    data = _read_vdf(lf)
    folders = ci(data, "libraryfolders")
    if not isinstance(folders, dict):
        return
    for entry in folders.values():
        if not isinstance(entry, dict):
            continue
        path = ci(entry, "path") or ""
        apps = ci(entry, "apps")
        if not isinstance(apps, dict):
            apps = entry["apps"] = {}
        if _same(path, old_lib):
            for k in [k for k in apps if k == str(appid)]:
                del apps[k]
        elif _same(path, new_lib):
            apps[str(appid)] = str(size)
    _write_vdf(lf, data)


def _tree_size(path):
    path = Path(path)
    if path.is_file() or path.is_symlink():
        return path.lstat().st_size
    return library._tree_size(path)


def move_game(root, appid, target, flatpak=True, progress=None):
    """Moves the game into the library `target`. -> "" on success, or what went wrong (a key of the texts):
    "not_found", "same_place", "unsupported", "exists", "no_space", "no_access", "copy_failed".
    The caller makes sure Steam is not running."""
    game = find_game(root, appid)
    if not game:
        return "not_found"
    src, target = game["library"], Path(target)
    if _same(src, target):
        return "same_place"
    if not library.supported_location(target):
        return "unsupported"
    parts = [p for p in _parts(appid, game["installdir"]) if (src / p).exists() or (src / p).is_symlink()]
    manifest_rel = f"steamapps/appmanifest_{appid}.acf"
    if any((target / p).exists() for p in parts + [manifest_rel]):
        return "exists"
    if not _same(target, root):
        ensure_library(root, target)
    if not grant_access(target, flatpak):
        return "no_access"
    same_fs = library._same_filesystem(src, target)
    total = sum(_tree_size(src / p) for p in parts)
    if not same_fs and shutil.disk_usage(library._existing(target)).free < total + SPARE_BYTES:
        return "no_space"

    moved = []
    try:
        for i, rel in enumerate(parts):
            if progress:
                progress(i, len(parts))
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if same_fs:
                os.rename(src / rel, dest)
                moved.append(rel)
                continue
            partial = dest.with_name(dest.name + PARTIAL)
            subprocess.run(["cp", "-a", "--reflink=auto", str(src / rel), str(partial)], check=True,
                           capture_output=True)
            if _tree_size(partial) < _tree_size(src / rel):
                raise OSError(f"the copy of {rel} is incomplete")
            partial.rename(dest)
            moved.append(rel)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("moving %s: %s", appid, e)
        # back to how it was: renamed parts go back, copies are deleted (the originals were not touched)
        for rel in moved:
            if same_fs:
                os.rename(target / rel, src / rel)
            else:
                _remove(target / rel)
        for rel in parts:
            _remove((target / rel).with_name((target / rel).name + PARTIAL))
        return "copy_failed"

    # the manifest last: until now Steam (and a later look) found the game in its old place
    shutil.copy2(game["manifest"], target / manifest_rel)
    game["manifest"].unlink()
    _set_app_library(root, appid, src, target, game["size"] or total)
    if not same_fs:
        for rel in parts:
            _remove(src / rel)
    log.info("moved %s (%s) from %s to %s", game["name"], appid, src, target)
    return ""


def _remove(path):
    path = Path(path)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
