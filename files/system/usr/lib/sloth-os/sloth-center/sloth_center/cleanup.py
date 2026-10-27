"""What "Clean up" may delete, measured first, so the user can review it item by item (Disks page).

The user's own parts are found and deleted here (no password): cache files not used for a month (~/.cache, except
Sloth OS's own folder: the Windows programs' logs that self-healing reads, and the shared knowledge), the Trash, and
the Windows installers in the home folder that a program was already installed from. The apps' unused components
(Flatpak) and the system's temporary files (rpm-ostree cleanup, with administrator approval) are run by disks.py.
"""
import os
import shutil
import time
from pathlib import Path

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache"))
TRASH = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "Trash"
CACHE_DAYS = 30
CACHE_KEEP = {"sloth-os"}


def _walk_files(folder):
    """Every file under the folder (links are not followed, nor counted)."""
    for root, dirs, names in os.walk(folder, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in names:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                yield path


def _size(path):
    try:
        return os.lstat(path).st_blocks * 512
    except OSError:
        return 0


def old_cache_files(cache=None, days=CACHE_DAYS, keep=CACHE_KEEP, now=None):
    """[(path, bytes)] of the cache files not changed or read for `days` days."""
    cache = Path(cache or CACHE)
    limit = (now or time.time()) - days * 86400
    out = []
    try:
        tops = list(cache.iterdir())
    except OSError:
        return out
    for top in tops:
        if top.name in keep or top.is_symlink():
            continue
        for path in ([str(top)] if top.is_file() else _walk_files(top)):
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if max(st.st_mtime, st.st_atime) < limit:
                out.append((path, st.st_blocks * 512))
    return out


def trash_size(trash=None):
    return sum(_size(p) for p in _walk_files(Path(trash or TRASH) / "files"))


def used_installers(installer_paths, home=None):
    """[(path, bytes)] of the installers a program was already installed from that are still in the home folder
    (not inside a program's own folder, not on another drive or a disc)."""
    home = Path(home or HOME).resolve()
    out, seen = [], set()
    for raw in installer_paths:
        if not raw:
            continue
        path = Path(raw)
        try:
            real = path.resolve()
        except OSError:
            continue
        if real in seen or not real.is_file():
            continue
        try:
            rel = real.relative_to(home)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in ("Applications", ".local", ".var", ".cache"):
            continue
        seen.add(real)
        out.append((str(real), _size(real)))
    return out


def delete_files(paths):
    """Deletes the files. -> bytes freed (as counted before)."""
    freed = 0
    for path, size in paths:
        try:
            os.remove(path)
            freed += size
        except OSError:
            pass
    return freed


def remove_empty_dirs(folder=None, keep=CACHE_KEEP):
    folder = Path(folder or CACHE)
    for root, dirs, files in os.walk(folder, topdown=False):
        if Path(root) == folder or Path(root).relative_to(folder).parts[0] in keep:
            continue
        try:
            os.rmdir(root)
        except OSError:
            pass


def empty_trash(trash=None):
    """Empties the Trash (its files and their notes, as the file manager does). -> bytes freed."""
    trash = Path(trash or TRASH)
    freed = trash_size(trash)
    for sub in ("files", "info"):
        folder = trash / sub
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except OSError:
                pass
    try:
        (trash / "directorysizes").unlink()
    except OSError:
        pass
    return freed
