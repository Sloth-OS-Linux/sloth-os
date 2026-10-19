"""Telepített Windows-programok: lista, indítás, fájlok, javítás, áthelyezés, eltávolítás, átvétel a Steamből.

A programok helye és adatai a közös sloth_common.apps-ban vannak (a .exe kezelő is azt használja):
alapból ~/Applications/<program>/. Telepíteni és indítani a .exe kezelő (sloth-exe) tud; ez az oldal
azt hívja. Nem kell hozzá rendszergazdai jog: minden a felhasználó saját mappájában van.
"""
import logging
import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot

from sloth_common import sharing
from sloth_common.apps import library, menu, steam

from .i18n import tr

log = logging.getLogger("sloth-center.winprograms")


def _size_text(nbytes):
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2)):
        if nbytes >= div:
            v = nbytes / div
            return (f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}") + f" {unit}"
    return tr("kevesebb mint 1 MB")


def _dir_size(path):
    """A mappa mérete; a hivatkozások (pl. a „Program fájljai”) nem számítanak kétszer."""
    total = 0
    for dirpath, _dirs, files in os.walk(path, followlinks=False):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def _pretty(path):
    """~/Applications a /home/<név>/Applications helyett."""
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


class WinProgramsController(QObject):
    changed = Signal()
    _sizes_ready = Signal(object)
    _work_done = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._sizes = {}
        self._busy = False
        self._message = ""
        self._steam = []
        self._sizes_ready.connect(self._on_sizes)
        self._work_done.connect(self._on_work_done)
        self.refresh()

    @Property("QVariantList", notify=changed)
    def programs(self):
        return [{**p, "size": self._sizes.get(p["id"], "")} for p in self._items]

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(str, notify=changed)
    def location(self):
        """Ide települnek az új programok."""
        return _pretty(library.default_library())

    @Property("QVariantList", notify=changed)
    def steamPrograms(self):
        """A Steamhez hozzáadott Windows-programok, amiket még nem vettünk át."""
        return self._steam

    @Property(bool, notify=changed)
    def sharing(self):
        """A közös tudás megosztása (sloth_exe/community.py): névtelen jelentés a bevált beállításokról."""
        return sharing.enabled()

    @Slot(bool)
    def setSharing(self, value):
        sharing.set_enabled(value)
        self.changed.emit()

    @Slot()
    def refresh(self):
        # A régi helyről (~/.local/share/sloth-os/windows-programs) egyszer áthozzuk az új könyvtárba
        try:
            library.migrate_legacy()
        except OSError as e:
            log.warning("átköltözés: %s", e)
        items = []
        default = library.default_library()
        apps = library.all_apps()
        for app in apps:
            entries = menu.entries(app)
            icon = next((e["icon"] for e in entries if e["icon"].startswith("/")), "")
            meta = app.meta
            installer = meta.get("installer", "")
            items.append({
                "id": app.id, "name": app.name, "kind": app.kind,
                "entries": [{"name": e["name"], "target": e["target"]} for e in entries],
                "icon": f"file://{icon}" if icon else "",
                "folder": _pretty(app.dir),
                "publisher": meta.get("publisher", ""),
                "shared": app.id == library.SHARED_ID,
                "canReinstall": bool(installer) and Path(installer).is_file(),
                "canMove": app.kind == "windows" and not app.legacy and app.dir.parent != default,
            })
        self._items = items
        self._steam = [{"appid": s["appid"], "name": s["name"], "canAdopt": steam.can_adopt(s)}
                       for s in steam.shortcuts() if not steam.imported(s["appid"])]
        self.changed.emit()
        # A méret kiszámolása lassú lehet, ezért háttérszálon megy
        dirs = {a.id: a.dir for a in apps}
        threading.Thread(target=lambda: self._sizes_ready.emit(
            {k: _size_text(_dir_size(d)) for k, d in dirs.items()}), daemon=True).start()

    def _on_sizes(self, sizes):
        self._sizes = sizes
        self.changed.emit()

    def _app(self, app_id):
        app = library.find(app_id)
        if app is None:
            log.warning("nincs ilyen program: %s", app_id)
        return app

    def _set_message(self, text):
        self._message = text
        self.changed.emit()

    def _run_in_background(self, work):
        """Hosszú művelet (eltávolítás, áthelyezés, átvétel) háttérszálon; a végén üzenet és frissítés."""
        self._busy = True
        self.changed.emit()

        def run():
            try:
                text = work()
            except Exception as e:  # a hiba ne akassza meg a felületet
                log.warning("művelet: %s", e)
                text = tr("Nem sikerült. Próbáld újra később.")
            self._work_done.emit(text or "")

        threading.Thread(target=run, daemon=True).start()

    def _on_work_done(self, text):
        self._busy = False
        self._message = text
        self.refresh()

    # --- Műveletek ---------------------------------------------------------------------------------

    @Slot(str)
    def install(self, url):
        """Telepítés egy kiválasztott .exe / .msi fájlból (a .exe kezelő végzi, mint dupla kattintásnál)."""
        path = QUrl(url).toLocalFile() if "://" in url else url
        if path:
            subprocess.Popen(["sloth-exe", path], start_new_session=True)

    @Slot(str)
    def launch(self, app_id):
        app = self._app(app_id)
        if app is None:
            return
        if app.kind == "steam":
            subprocess.Popen(steam.launch_command(app), start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        target = next((e["target"] for e in menu.entries(app) if e["target"]), None)
        if target:
            subprocess.Popen(["sloth-exe", "--launch", app.id, target], start_new_session=True)
        else:
            self.editShortcuts(app_id)

    @Slot(str)
    def openFolder(self, app_id):
        """A program mappája a Dolphinban (benne a „Program fájljai” a telepített fájlokkal)."""
        app = self._app(app_id)
        if app is not None:
            subprocess.Popen(["xdg-open", str(app.dir)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str)
    def editShortcuts(self, app_id):
        """A .exe kezelő szerkesztő ablaka: mi legyen a Start menüben (a lehetséges indítók felismerve)."""
        app = self._app(app_id)
        if app is None or app.kind != "windows":
            return
        proc = subprocess.Popen(["sloth-exe", "--shortcuts", app.id])
        threading.Thread(target=lambda: (proc.wait(), self._work_done.emit("")), daemon=True).start()

    @Slot(str)
    def repair(self, app_id):
        """Javítás: a megjegyzett indítási beállítások törlése; a következő indításkor újra megkeresi a működőt."""
        app = self._app(app_id)
        if app is None or app.kind != "windows":
            return
        if app.busy():
            self._set_message(tr("{name} most fut. Zárd be, és utána próbáld újra.", name=app.name))
            return
        app.save_meta(launch={})
        self._set_message(tr("Kész. A következő indításkor {name} újra megkeresi a neki működő beállítást.",
                             name=app.name))

    @Slot(str)
    def reinstall(self, app_id):
        """Újratelepítés ugyanabba a mappába (a beállítások és a mentések megmaradnak)."""
        app = self._app(app_id)
        installer = (app.meta.get("installer") if app else "") or ""
        if installer and Path(installer).is_file():
            subprocess.Popen(["sloth-exe", installer], start_new_session=True)

    @Slot(str)
    def remove(self, app_id):
        """Program, Start menü bejegyzései és naplója."""
        app = self._app(app_id)
        if app is None:
            return
        if app.busy():
            self._set_message(tr("{name} most fut. Zárd be, és utána próbáld újra.", name=app.name))
            return
        name = app.name
        self._items = [p for p in self._items if p["id"] != app_id]
        self._run_in_background(
            lambda: "" if library.remove(app) else tr("{name} nem távolítható el innen.", name=name))

    @Slot(str)
    def setLocation(self, url):
        """Az új programok helye (pl. egy másik meghajtó). A meglévők maradnak, egyenként áthelyezhetők."""
        path = Path(QUrl(url).toLocalFile() if "://" in url else url)
        if not library.supported_location(path):
            self._set_message(tr("Ez a meghajtó Windows-formátumú (NTFS, exFAT vagy FAT). Ide nem telepíthetők "
                                 "programok; válassz egy Linuxos meghajtót vagy mappát."))
            return
        library.set_default_library(path)
        self._set_message(tr("Az új programok ide települnek: {path}", path=_pretty(path)))
        self.refresh()

    @Slot(str)
    def move(self, app_id):
        """Áthelyezés az új programok helyére (a Start menü bejegyzései érvényesek maradnak)."""
        app = self._app(app_id)
        if app is None:
            return
        if app.busy():
            self._set_message(tr("{name} most fut. Zárd be, és utána próbáld újra.", name=app.name))
            return
        target = library.default_library()
        name = app.name
        self._run_in_background(
            lambda: tr("{name} áthelyezve ide: {path}", name=name, path=_pretty(target))
            if library.move(app, target) else tr("{name} áthelyezése nem sikerült. A program a régi helyén maradt, "
                                                 "és ott ugyanúgy működik.", name=name))

    @Slot(int, bool)
    def importSteam(self, appid, adopt):
        """Steamhez hozzáadott program átvétele: a Steamen keresztül (link), vagy saját másolattal (adopt)."""
        sc = next((s for s in steam.shortcuts() if s["appid"] == appid), None)
        if sc is None:
            return
        if not adopt:
            steam.link(sc)
            self._set_message(tr("{name} mostantól itt is megtalálható; a Steam indítja, ahogy eddig.",
                                 name=sc["name"]))
            self.refresh()
            return
        if steam.prefix_in_use(sc["prefix"]):
            self._set_message(tr("{name} most fut a Steamben. Zárd be, és utána próbáld újra.", name=sc["name"]))
            return

        def work():
            app = steam.adopt(sc, tr("Program fájljai"))
            if app is None:
                return tr("{name} átvétele nem sikerült. A Steamben minden maradt a régiben.", name=sc["name"])
            return tr("{name} átvéve. Mostantól a Steam nélkül is indul; a Steamben lévő példányhoz nem nyúltunk.",
                      name=sc["name"])

        self._run_in_background(work)
