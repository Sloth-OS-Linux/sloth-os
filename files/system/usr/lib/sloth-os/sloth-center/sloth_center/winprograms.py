"""Telepített Windows-programok: lista, méret, eltávolítás.

Ugyanazt a mappaszerkezetet olvassa, amit a .exe kezelő (sloth-exe) hoz létre:
~/.local/share/sloth-os/windows-programs/<program>/ és a sloth-win-*.desktop bejegyzések.
Nem kell hozzá rendszergazdai jog: minden a felhasználó saját mappájában van.
"""
import configparser
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

log = logging.getLogger("sloth-center.winprograms")

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
ROOT = DATA_HOME / "sloth-os" / "windows-programs"
APPS_DIR = DATA_HOME / "applications"


def _size_text(nbytes):
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2)):
        if nbytes >= div:
            v = nbytes / div
            return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + f" {unit}"
    return "kevesebb mint 1 MB"


def _dir_size(path):
    total = 0
    for dirpath, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def _menu_entries(slug):
    out = []
    for desktop in sorted(APPS_DIR.glob(f"sloth-win-{slug}-*.desktop")):
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        try:
            cp.read(desktop, encoding="utf-8")
            entry = cp["Desktop Entry"]
            if entry.get("X-Sloth-Program") != slug:
                continue
            out.append({"name": entry.get("Name", desktop.stem), "icon": entry.get("Icon", ""),
                        "desktop": str(desktop)})
        except (configparser.Error, KeyError, OSError):
            continue
    return out


class WinProgramsController(QObject):
    changed = Signal()
    _sizes_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._sizes = {}
        self._busy = False
        self._sizes_ready.connect(self._on_sizes)
        self.refresh()

    @Property("QVariantList", notify=changed)
    def programs(self):
        return [{**p, "size": self._sizes.get(p["slug"], "")} for p in self._items]

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Slot()
    def refresh(self):
        items = []
        if ROOT.is_dir():
            for d in sorted(ROOT.iterdir()):
                if not d.is_dir():
                    continue
                try:
                    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    meta = {}
                entries = _menu_entries(d.name)
                icon = next((e["icon"] for e in entries if e["icon"].startswith("/")), "")
                items.append({"slug": d.name, "name": meta.get("name") or d.name,
                              "entries": entries, "icon": f"file://{icon}" if icon else ""})
        self._items = items
        self.changed.emit()
        # A méret kiszámolása lassú lehet, ezért háttérszálon megy
        threading.Thread(target=lambda: self._sizes_ready.emit(
            {p["slug"]: _size_text(_dir_size(ROOT / p["slug"])) for p in items}), daemon=True).start()

    def _on_sizes(self, sizes):
        self._sizes = sizes
        # a Start menü bejegyzések változhattak (pl. a szerkesztő ablak után)
        for p in self._items:
            p["entries"] = _menu_entries(p["slug"])
        self.changed.emit()

    @Slot(str)
    def editShortcuts(self, slug):
        """A .exe kezelő szerkesztő ablaka: mi legyen a Start menüben."""
        if (ROOT / slug).is_dir():
            proc = subprocess.Popen(["sloth-exe", "--shortcuts", slug])
            threading.Thread(target=lambda: (proc.wait(), self._sizes_ready.emit(self._sizes), None),
                             daemon=True).start()

    @Slot(str)
    def remove(self, slug):
        """Program és Start menü bejegyzéseinek törlése."""
        target = (ROOT / slug).resolve()
        if target.parent != ROOT.resolve() or not target.is_dir():
            log.warning("érvénytelen program: %s", slug)
            return
        for e in _menu_entries(slug):
            try:
                Path(e["desktop"]).unlink()
            except OSError:
                pass
        self._busy = True
        self.changed.emit()

        def work():
            shutil.rmtree(target, ignore_errors=True)
            self._sizes_ready.emit(self._sizes)

        threading.Thread(target=work, daemon=True).start()
        self._items = [p for p in self._items if p["slug"] != slug]
        self._busy = False
        self.changed.emit()
