"""A Windows-oldali rendszerindítási segéd elhelyezése a Windows-partíción (Windows mellé telepített gépeken).

A segéd (/usr/share/sloth-os/windows-helper) a Windows Nyilvános asztalára kerül („Sloth OS” mappa); a
felhasználó a Windowsban egyszer duplán rákattint, és onnantól a Windows minden induláskor visszateszi a
Sloth OS-t a rendszerindítási sorrend elejére, ha egy Windows-frissítés elé tette volna magát.
A partíciót a UDisksen keresztül csatoljuk (felhasználóként; belső lemeznél jelszót kérhet), és ha mi
csatoltuk, utána le is választjuk. Hibernált vagy „gyors indítással” leállított Windows partíciója csak
olvasható: ilyenkor szólunk, mit kell tenni.
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
    """Az NTFS fájlrendszerek: [(D-Bus út, csatolási pontok)]."""
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
    """-> "placed" | "readonly" (a Windows hibernált / gyors indítással állt le) | "none" (nincs Windows)"""
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
            log.warning("csatolás (%s): %s", path, e.message)
            readonly = readonly or "read-only" in e.message.lower() or "hibernat" in e.message.lower()
            continue
        try:
            if not (mnt / "Windows/System32").is_dir():
                continue
            dest = mnt / DEST
            dest.mkdir(parents=True, exist_ok=True)
            for f in HELPER_DIR.iterdir():
                shutil.copyfile(f, dest / f.name)
            log.info("a Windows-segéd elhelyezve: %s", dest)
            return "placed"
        except OSError as e:
            log.warning("másolás (%s): %s", mnt, e)
            readonly = True
        finally:
            if mounted_by_us:
                try:
                    _call(bus, path, "Unmount", {})
                except GLib.Error as e:
                    log.warning("leválasztás: %s", e.message)
    return "readonly" if readonly else "none"
