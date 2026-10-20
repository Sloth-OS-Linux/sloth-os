"""„Korábbi verziók”: egy fájl vagy mappa mentett állapotai (Dolphin, jobb klikk; sloth-versions <út>).

A mentett állapotok a saját fájlok óránkénti pillanatképei (sloth_common.snapshots), csak olvashatók. Innen:
  Megnyitás           a régi változat megnyitása (mappánál a fájlkezelőben, onnan bármi kimásolható)
  Visszaállítás       a régi változat a helyére kerül; a mostani a Kukába (onnan visszahozható). Mappánál a
                      megváltozott és a törölt fájlok jönnek vissza, az azóta létrehozottak megmaradnak
  Törölt elemek       mappánál csak az azóta törölt fájlok visszahozása (a meglévőkhöz nem nyúl)
  Mentés másolatként  a régi változat a mostani mellé, a dátummal a nevében
A másolás reflinkkel megy (azonnali, nem foglal új helyet), jelszó nélkül: mindenki a saját fájljait állítja vissza.
"""
import datetime
import fcntl
import logging
import os
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QObject, Property, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from sloth_common import snapshots as snap

from . import texts
from .i18n import Translator, catalog, tr

log = logging.getLogger("sloth-versions")

QML_DIR = Path(__file__).resolve().parent / "qml"
FICLONE = 0x40049409
# Mappáknál ennyi elemig számoljuk meg, mi törlődött azóta (nagy mappánál nem számolunk)
COUNT_LIMIT = 20000


def clone(src, dst):
    """Egy fájl (vagy szimbolikus link) másolása reflinkkel, ha lehet; a jogok és az időpontok is."""
    if os.path.islink(src):
        os.symlink(os.readlink(src), dst)
        return
    with open(src, "rb") as fsrc, open(dst, "xb") as fdst:
        try:
            fcntl.ioctl(fdst.fileno(), FICLONE, fsrc.fileno())
        except OSError:
            shutil.copyfileobj(fsrc, fdst, 1024 * 1024)
    shutil.copystat(src, dst)


def same(a, b):
    """Ugyanaz-e a két fájl (méret, módosítás ideje, típus)."""
    try:
        sa, sb = os.lstat(a), os.lstat(b)
    except OSError:
        return False
    return (stat.S_IFMT(sa.st_mode) == stat.S_IFMT(sb.st_mode) and sa.st_size == sb.st_size
            and sa.st_mtime_ns == sb.st_mtime_ns)


def move_to_trash(path):
    """A fájl a Kukába (freedesktop.org Trash, ugyanaz, amit a Dolphin mutat; onnan visszaállítható).

    A Qt QFile.moveToTrash-e a próbán (Btrfs, külön subvolume-okkal) nem találta a Kukát."""
    trash = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "Trash"
    files, info = trash / "files", trash / "info"
    files.mkdir(parents=True, exist_ok=True, mode=0o700)
    info.mkdir(parents=True, exist_ok=True, mode=0o700)
    stem, suffix = (path.stem, path.suffix) if not path.is_dir() else (path.name, "")
    for n in range(1, 1000):
        name = path.name if n == 1 else f"{stem}.{n}{suffix}"
        try:
            fd = os.open(info / f"{name}.trashinfo", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        if os.path.lexists(files / name):
            os.close(fd)
            os.unlink(info / f"{name}.trashinfo")
            continue
        date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"[Trash Info]\nPath={quote(str(path))}\nDeletionDate={date}\n")
        try:
            os.rename(path, files / name)
        except OSError:
            os.unlink(info / f"{name}.trashinfo")
            raise
        return
    raise OSError(f"nem került a Kukába: {path}")


def replace_with(old, current):
    """A régi fájl a helyére; a mostani a Kukába. Előbb a másolat készül el, így hiba esetén nem vész el semmi."""
    tmp = current.with_name(f".{current.name}.sloth-restore")
    if os.path.lexists(tmp):
        os.unlink(tmp)
    clone(old, tmp)
    if os.path.lexists(current):
        try:
            move_to_trash(current)
        except OSError:
            os.unlink(tmp)
            raise
    os.rename(tmp, current)


def merge(old_dir, current_dir, only_missing):
    """Egy régi mappa visszaállítása a mostanira. (visszaállított, kimaradt) elemek száma."""
    restored = failed = 0
    for root, dirs, files in os.walk(old_dir):
        rel = Path(root).relative_to(old_dir)
        target_root = current_dir / rel
        for d in dirs:
            src, dst = Path(root) / d, target_root / d
            if os.path.islink(src):
                files.append(d)
            elif not os.path.lexists(dst):
                try:
                    os.makedirs(dst)
                    shutil.copystat(src, dst)
                    restored += 1
                except OSError as e:
                    log.warning("%s: %s", dst, e)
                    failed += 1
        dirs[:] = [d for d in dirs if not os.path.islink(Path(root) / d) and (target_root / d).is_dir()]
        for f in files:
            src, dst = Path(root) / f, target_root / f
            exists = os.path.lexists(dst)
            if (exists and only_missing) or (exists and same(src, dst)) or os.path.isdir(dst):
                continue
            try:
                replace_with(src, dst)
                restored += 1
            except OSError as e:
                log.warning("%s: %s", dst, e)
                failed += 1
    return restored, failed


def count_deleted(old_dir, current_dir):
    """Hány elem van a régi mappában, ami most hiányzik; -1, ha túl nagy a mappa a számoláshoz."""
    seen = missing = 0
    for root, dirs, files in os.walk(old_dir):
        rel = Path(root).relative_to(old_dir)
        for name in dirs + files:
            seen += 1
            if seen > COUNT_LIMIT:
                return -1
            if not os.path.lexists(current_dir / rel / name):
                missing += 1
        # a hiányzó mappa tartalmát nem számoljuk külön (a mappa egy elem)
        dirs[:] = [d for d in dirs if os.path.lexists(current_dir / rel / d)]
    return missing


def copy_name(path, when):
    """"Levél.odt" -> "Levél (2026-10-19 14.00).odt"; ha foglalt, sorszámmal."""
    stamp = when.astimezone().strftime("%Y-%m-%d %H.%M")
    stem, suffix = (path.stem, path.suffix) if path.is_file() else (path.name, "")
    for i in range(1, 100):
        extra = f" {i}" if i > 1 else ""
        candidate = path.with_name(f"{stem} ({stamp}{extra}){suffix}")
        if not os.path.lexists(candidate):
            return candidate
    raise OSError("nincs szabad név")


class VersionsController(QObject):
    changed = Signal()
    _done = Signal(str)          # a háttérszálból: kész szöveg vagy hiba (a "!" előtag hibát jelez)
    _counted = Signal(int, int, int)  # (lista-generáció, sor, azóta törölt elemek száma)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = Path(os.path.abspath(path))
        self._is_dir = self._path.is_dir() and not self._path.is_symlink()
        self._problem = ""
        self._versions = []
        self._busy = False
        self._error = ""
        self._info = ""
        self._generation = 0
        self._done.connect(self._on_done)
        self._counted.connect(self._on_counted)
        self.refresh()

    fileName = Property(str, lambda self: self._path.name or str(self._path), constant=True)
    folder = Property(str, lambda self: str(self._path.parent), constant=True)
    isDir = Property(bool, lambda self: self._is_dir, constant=True)
    problem = Property(str, lambda self: self._problem, notify=changed)
    enabled = Property(bool, lambda self: snap.load_config()["enabled"], notify=changed)
    versions = Property("QVariantList", lambda self: list(self._versions), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Slot()
    def refresh(self):
        self._versions = []
        self._generation += 1
        state = snap.state()
        rel, problem = snap.locate(self._path) if state == "ready" else (None, state)
        self._problem = problem
        if rel is not None:
            self._versions = self._file_versions(rel) if not self._is_dir else self._dir_versions(rel)
            if not self._versions:
                self._problem = "none"
        self.changed.emit()
        if self._is_dir and self._versions:
            threading.Thread(target=self._count_all, args=(self._generation, list(self._versions)),
                             daemon=True).start()

    def _row(self, name, when, path, **extra):
        return {"name": name, "when": when.timestamp(), "dateText": texts.datetime_text(when),
                "path": str(path), **extra}

    def _file_versions(self, rel):
        """Fájlnál csak a különböző változatok (az egymás utáni egyformákból a legújabb)."""
        rows, last = [], None
        for name, when, path in snap.versions_of(rel):
            try:
                st = os.lstat(path)
            except OSError:
                continue
            key = (st.st_size, st.st_mtime_ns)
            if key == last:
                continue
            last = key
            current = same(path, self._path)
            detail = texts.size_text(st.st_size) + (" · " + tr("Ugyanaz, mint a mostani") if current else "")
            rows.append(self._row(name, when, path, detail=detail, current=current, deleted=0))
        return rows

    def _dir_versions(self, rel):
        return [self._row(name, when, path, detail="", current=False, deleted=-1)
                for name, when, path in snap.versions_of(rel) if path.is_dir()]

    def _count_all(self, generation, rows):
        for i, row in enumerate(rows):
            if generation != self._generation:
                return
            self._counted.emit(generation, i, count_deleted(Path(row["path"]), self._path))

    def _on_counted(self, generation, i, n):
        if generation == self._generation:
            row = dict(self._versions[i], deleted=n)
            if n > 0:
                row["detail"] = tr("{n} azóta törölt elem", n=n)
            self._versions[i] = row
            self.changed.emit()

    def _work(self, fn):
        if self._busy:
            return
        self._busy, self._error, self._info = True, "", ""
        self.changed.emit()

        def run():
            try:
                self._done.emit(fn())
            except OSError as e:
                log.warning("%s", e)
                self._done.emit("!" + tr("Nem sikerült visszaállítani. A mostani fájljaidhoz nem nyúltam."))

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, text):
        self._busy = False
        if text.startswith("!"):
            self._error = text[1:]
        else:
            self._info = text
        self.refresh()

    def _merge_text(self, restored, failed):
        if failed:
            return "!" + tr("Nem sikerült mindent visszaállítani: {n} elem kimaradt.", n=failed)
        return tr("Kész: {n} elem visszaállítva.", n=restored)

    @Slot(int)
    def open(self, i):
        subprocess.Popen(["xdg-open", self._versions[i]["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(int)
    def restore(self, i):
        old = Path(self._versions[i]["path"])
        if self._is_dir:
            self._work(lambda: self._merge_text(*merge(old, self._path, only_missing=False)))
        else:
            def work():
                replace_with(old, self._path)
                return tr("Kész: visszaállítva. A felülírt változat a Kukában van.")
            self._work(work)

    @Slot(int)
    def restoreDeleted(self, i):
        old = Path(self._versions[i]["path"])
        self._work(lambda: self._merge_text(*merge(old, self._path, only_missing=True)))

    @Slot(int)
    def saveCopy(self, i):
        row = self._versions[i]
        when = datetime.datetime.fromtimestamp(row["when"], datetime.timezone.utc)

        def work():
            target = copy_name(self._path, when)
            r = subprocess.run(["cp", "-a", "--reflink=auto", "--", row["path"], str(target)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise OSError(r.stderr.strip())
            return tr("Kész: a másolat neve „{name}”.", name=target.name)
        self._work(work)

    @Slot()
    def openSettings(self):
        subprocess.Popen(["sloth-center", "--page", "backup"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "org.kde.desktop")
    paths = [a for a in sys.argv[1:] if not a.startswith("-")]
    app = QApplication(sys.argv)
    app.setApplicationName("sloth-versions")
    app.setApplicationDisplayName(tr("Korábbi verziók"))
    if catalog.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setOrganizationDomain("slothos.org")
    app.setDesktopFileName("org.slothos.center")
    app.setWindowIcon(QIcon.fromTheme("view-history"))
    if not paths:
        print("használat: sloth-versions <fájl vagy mappa>", file=sys.stderr)
        return 2
    # a Dolphin file:// címet is adhat
    path = QUrl(paths[0]).toLocalFile() if paths[0].startswith("file:") else paths[0]
    engine = QQmlApplicationEngine()
    controller = VersionsController(path)
    # változóban kell tartani: különben a Python eltakarítja, és a QML-ben minden szöveg üres
    translator = Translator()
    engine.rootContext().setContextProperty("L", translator)
    engine.rootContext().setContextProperty("versions", controller)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "VersionsWindow.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()
