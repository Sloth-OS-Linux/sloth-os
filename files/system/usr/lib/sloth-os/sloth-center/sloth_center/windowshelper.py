"""Placing the Windows-side boot helper on the Windows partition (on machines installed next to Windows).

The helper (/usr/share/sloth-os/windows-helper) goes on the Windows Public Desktop (a "Sloth OS" folder); the
user double-clicks it once in Windows, and from then on Windows puts Sloth OS back at the front of the boot
order on every start, if a Windows update had put itself in front.
The partition is mounted through UDisks (as the user; for an internal disk it may ask for a password), and if we
mounted it, we unmount it afterwards. The partition of a hibernated Windows or one shut down with "fast startup" is
read-only: then we say what to do.
"""
import logging
import shutil
from pathlib import Path

from gi.repository import Gio, GLib

log = logging.getLogger("sloth-center.windowshelper")

HELPER_DIR = Path("/usr/share/sloth-os/windows-helper")
UD = "org.freedesktop.UDisks2"
DEST = Path("Users/Public/Desktop/Sloth OS")


def _objects(bus):
    return bus.call_sync(UD, "/org/freedesktop/UDisks2", "org.freedesktop.DBus.ObjectManager",
                         "GetManagedObjects", None, None, Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]


def ntfs_filesystems():
    """The NTFS file systems: [(D-Bus path, mount points)]."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        objs = _objects(bus)
    except GLib.Error as e:
        log.warning("udisks: %s", e.message)
        return []
    out = []
    for path, ifs in objs.items():
        block, fs = ifs.get(UD + ".Block"), ifs.get(UD + ".Filesystem")
        if block and fs is not None and block.get("IdType") == "ntfs" and not block.get("HintIgnore"):
            mounts = [bytes(m).rstrip(b"\0").decode(errors="replace") for m in fs.get("MountPoints", [])]
            out.append((path, mounts))
    return out


def _call(bus, path, method, options):
    return bus.call_sync(UD, path, UD + ".Filesystem", method, GLib.Variant("(a{sv})", (options,)),
                         None, Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 60000, None)


def place():
    """-> "placed" | "readonly" (Windows was hibernated / shut down with fast startup) | "none" (no Windows)"""
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    readonly = False
    for path, mounts in ntfs_filesystems():
        mounted_by_us = False
        try:
            if mounts:
                mnt = Path(mounts[0])
            else:
                mnt = Path(_call(bus, path, "Mount", {}).unpack()[0])
                mounted_by_us = True
        except GLib.Error as e:
            log.warning("mounting (%s): %s", path, e.message)
            readonly = readonly or "read-only" in e.message.lower() or "hibernat" in e.message.lower()
            continue
        try:
            if not (mnt / "Windows/System32").is_dir():
                continue
            dest = mnt / DEST
            dest.mkdir(parents=True, exist_ok=True)
            for f in HELPER_DIR.iterdir():
                shutil.copyfile(f, dest / f.name)
            log.info("Windows helper placed: %s", dest)
            return "placed"
        except OSError as e:
            log.warning("copying (%s): %s", mnt, e)
            readonly = True
        finally:
            if mounted_by_us:
                try:
                    _call(bus, path, "Unmount", {})
                except GLib.Error as e:
                    log.warning("unmounting: %s", e.message)
    return "readonly" if readonly else "none"
