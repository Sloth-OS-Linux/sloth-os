"""Appok telepítése a libflatpak-kal, külön szálon, folyamatjelzéssel.

Az appok egyesével, a kiválasztás sorrendjében (a listán fentről lefelé) települnek,
mindegyik a saját tranzakciójában, a függőségeivel együtt. Előtte egy próbatranzakció
felméri a teljes letöltendő méretet; a felület csak azt látja, melyik app települ, és
hogy az összes letöltésből mennyi van meg (a futtatókörnyezeteket nem nevezzük meg).
"""
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import gi

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, Gio, GLib  # noqa: E402

from . import catalog  # noqa: E402
from .i18n import tr  # noqa: E402

log = logging.getLogger("sloth-welcome.installer")

FLATHUB = "flathub"
FLATHUB_REPO_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
USER_AGENT = "SlothOS-Welcome/1.0"
# A Flathub-os hibák nagy része átmeneti hálózati gond, ezért újrapróbáljuk
MAX_ATTEMPTS = 3
MB = 1024 * 1024
# A hibák fordítási kulcsként utaznak; a felület mutatja őket a választott nyelven
NETWORK_ERROR = "error.network"


def _human_error(raw):
    low = (raw or "").lower()
    if any(k in low for k in ("could not resolve", "network", "timed out", "timeout", "connection", "unreachable")):
        return NETWORK_ERROR
    if any(k in low for k in ("no space", "enospc")):
        return "error.disk_full"
    if any(k in low for k in ("not authorized", "authentication", "permission")):
        return "error.not_authorized"
    if "checksum" in low or "ellenőrző" in low:
        return "error.checksum"
    return "error.generic"


def _http_get(url, on_chunk=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        chunks, done = [], 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            done += len(chunk)
            if on_chunk:
                on_chunk(done, total)
        return b"".join(chunks)


# A Windows-programok (pl. játékindítók) letöltött telepítői; a varázsló után innen nyílnak meg egyesével
WINDOWS_INSTALLERS = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "welcome-installers"


def _remote_size(url):
    """A letöltendő fájl mérete (HEAD, átirányítással); ha a szerver nem mondja meg, 0."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except (OSError, ValueError):
        return 0


def download_windows_installer(app, on_bytes=None):
    """A Windows-program hivatalos telepítője a WINDOWS_INSTALLERS mappába (fájlba írva, nem a memóriába). -> út"""
    WINDOWS_INSTALLERS.mkdir(parents=True, exist_ok=True)
    dest = WINDOWS_INSTALLERS / app["file"]
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(app["url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as f:
        done = 0
        while True:
            chunk = resp.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if on_bytes:
                on_bytes(done)
    part.replace(dest)
    return dest


STATE_FILE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "github-bundles.json"


def bundle_versions():
    """A GitHub-csomagként telepített appok verziói: {app_id: kiadás címkéje}."""
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_bundle_version(app_id, tag):
    data = bundle_versions()
    data[app_id] = tag
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def latest_release(app):
    return json.loads(_http_get(f"https://api.github.com/repos/{app['repo']}/releases/latest"))


def bundle_asset(app, release):
    """A kiadás Flatpak csomagja: {name, browser_download_url, size, …} vagy None."""
    return next((a for a in release.get("assets", []) if a["name"].endswith(app["asset_suffix"])), None)


def download_latest_bundle(app, on_status=lambda *a: None, release=None, on_bytes=None):
    """Legfrissebb Flatpak csomag a GitHub kiadásból, SHA256 ellenőrzéssel. -> (fájl, címke)"""
    name = app["name"]
    on_status(tr("install.downloading", name=name), "", -1)
    release = release or latest_release(app)
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    bundle = bundle_asset(app, release)
    bundle_name = bundle["name"] if bundle else None
    if not bundle_name or "SHA256SUMS.txt" not in assets:
        raise RuntimeError(f"{name}: nincs megfelelő csomag a kiadásban")
    sums = _http_get(assets["SHA256SUMS.txt"]).decode("utf-8", "replace")
    expected = next((line.split()[0] for line in sums.splitlines()
                     if line.strip().endswith(bundle_name)), None)

    def progress(done, total):
        if on_bytes:
            on_bytes(done)
        pct = int(done * 100 / total) if total else -1
        on_status(tr("install.downloading", name=name), tr("install.mb", mb=done // (1024 * 1024)), pct)

    data = _http_get(assets[bundle_name], progress)
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("checksum: a letöltött csomag ellenőrző összege nem egyezik")
    fd, path = tempfile.mkstemp(suffix=".flatpak", prefix="sloth-bundle-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path, release.get("tag_name", "")


class Installer:
    """A callbackek a háttérszálból hívódnak; a hívó gondoskodik a szálváltásról."""

    def __init__(self, on_status, on_app_state, on_finished):
        self._on_status = on_status          # (szöveg, részletek, összesített 0..100 vagy -1)
        self._on_app_state = on_app_state    # (app_id, "installing" | "done" | "failed", hibakulcs)
        self._on_finished = on_finished      # (sikeres_idk, sikertelen {id: hibakulcs})
        self._thread = None
        self._bundle_tags = {}
        self.windows_installers = {}  # app_id -> a letöltött telepítő útja (a varázsló után nyílnak meg)
        self._progress = {"total": 0, "done": 0}  # bájtban, az összes kiválasztott appra

    def start(self, app_ids):
        self._thread = threading.Thread(target=self._run, args=(list(app_ids),), daemon=True)
        self._thread.start()

    # --- Belső -------------------------------------------------------------

    def _ensure_flathub(self, inst):
        try:
            inst.get_remote_by_name(FLATHUB, None)
            return
        except GLib.Error:
            pass
        data = _http_get(FLATHUB_REPO_URL)
        remote = Flatpak.Remote.new_from_file(FLATHUB, GLib.Bytes.new(data))
        inst.add_remote(remote, True, None)

    @staticmethod
    def _ref(app_id):
        return f"app/{app_id}/{Flatpak.get_default_arch()}/stable"

    def _report(self, name, index, count, current=0, frac=0.0):
        """Állapot: melyik app települ, és az összes letöltésből mennyi van meg.

        current: a folyamatban lévő letöltés bájtjai; frac: az app saját haladása 0..1
        (csak akkor számít, ha a teljes méretet nem sikerült felmérni).
        """
        done = self._progress["done"] + current
        total = max(self._progress["total"], done)
        if self._progress["total"]:
            overall = int(done * 100 / total)
            detail = f"{tr('install.mb', mb=done // MB)} / {tr('install.mb', mb=total // MB)}"
        else:
            overall = int((index + frac) * 100 / max(1, count))
            detail = tr("install.mb_downloaded", mb=done // MB) if done >= MB else ""
        self._on_status(tr("install.installing", name=name), detail, min(99, overall))

    def _plan(self, inst, apps, failed):
        """A teljes letöltendő méret felmérése. -> {app_id: GitHub-kiadás} a csomagos appokhoz

        A Flathubos appokat egy próbatranzakcióba tesszük, amelyet a „ready” jelnél (a méretek
        ismeretében, letöltés előtt) leállítunk; a közös futtatókörnyezet így csak egyszer számít.
        """
        self._progress = {"total": 0, "done": 0}
        releases, total = {}, 0
        flathub = [a for a in apps if a.get("source", "flathub") == "flathub"]
        if flathub:
            sizes = {}

            def on_ready(t):
                for op in t.get_operations():
                    sizes[op.get_ref()] = op.get_download_size()
                return False  # csak felmérés, itt még nem telepítünk

            txn = Flatpak.Transaction.new_for_installation(inst, None)
            txn.add_default_dependency_sources()
            for app in flathub:
                try:
                    txn.add_install(FLATHUB, self._ref(app["id"]), None)
                except GLib.Error:
                    pass  # pl. már telepítve; a telepítésnél kiderül
            txn.connect("ready", on_ready)
            try:
                txn.run(None)
            except GLib.Error as e:
                if not sizes:
                    log.info("a méret felmérése nem sikerült: %s", e.message)
            total += sum(sizes.values())
        for app in apps:
            if app.get("source") == "windows":
                total += _remote_size(app["url"])
                continue
            if app.get("source") != "github-bundle":
                continue  # a "system" appok nem töltenek le semmit
            try:
                releases[app["id"]] = latest_release(app)
            except Exception as e:
                log.warning("%s: %s", app["id"], e)
                failed[app["id"]] = _human_error(str(e))
                self._on_app_state(app["id"], "failed", failed[app["id"]])
                continue
            asset = bundle_asset(app, releases[app["id"]])
            total += asset.get("size", 0) if asset else 0
        self._progress["total"] = total
        return releases

    def _download_bundle(self, app, release, index, count):
        def on_bytes(n):
            self._report(app["name"], index, count, current=n)

        path, tag = download_latest_bundle(app, release=release, on_bytes=on_bytes)
        self._progress["done"] += os.path.getsize(path)
        self._bundle_tags[app["id"]] = tag
        return path

    def _run(self, app_ids):
        ok, failed = [], {}
        for attempt in range(MAX_ATTEMPTS):
            # Csak a még nem telepített és hálózati hiba miatt elbukott appokat próbáljuk újra
            pending = [a for a in app_ids if a not in ok and (a not in failed or failed[a] == NETWORK_ERROR)]
            if not pending:
                break
            if attempt:
                self._on_status(tr("install.retrying"), "", -1)
                time.sleep(5 * attempt)
            for a in pending:
                failed.pop(a, None)
            self._attempt(pending, ok, failed)
        self._on_finished(ok, failed)

    def _attempt(self, app_ids, ok, failed):
        temp_files = []
        try:
            inst = Flatpak.Installation.new_system(None)
            self._on_status(tr("install.preparing"), "", -1)
            self._ensure_flathub(inst)
            apps = [app for app in map(catalog.find_app, app_ids) if app]
            releases = self._plan(inst, apps, failed)
            todo = [app for app in apps if app["id"] not in failed]
            user_inst = None
            # Egyesével, a lista sorrendjében: mindig csak egy app áll „telepítés alatt”
            for index, app in enumerate(todo):
                app_id = app["id"]
                self._on_app_state(app_id, "installing", "")
                self._report(app["name"], index, len(todo))
                try:
                    if app.get("source") == "windows":
                        def on_bytes(n, app=app, index=index):
                            self._report(app["name"], index, len(todo), current=n)
                        path = download_windows_installer(app, on_bytes)
                        self._progress["done"] += path.stat().st_size
                        self.windows_installers[app_id] = path
                        error = None
                    elif app.get("source") == "system":
                        # már a rendszerben van, csak bekapcsoljuk (pl. KDE Connect: /usr/libexec/sloth-os/phone-link)
                        r = subprocess.run([app["switch"], "on"], capture_output=True, text=True, timeout=60)
                        error = None if r.returncode == 0 else (r.stderr.strip() or f"exit {r.returncode}")
                    elif app.get("source") == "github-bundle":
                        # A GitHub-csomagok a felhasználóhoz kerülnek, így a háttérfrissítésükhöz nem kell jelszó
                        if user_inst is None:
                            user_inst = Flatpak.Installation.new_user(None)
                            self._ensure_flathub(user_inst)
                        path = self._download_bundle(app, releases[app_id], index, len(todo))
                        temp_files.append(path)
                        txn = Flatpak.Transaction.new_for_installation(user_inst, None)
                        txn.add_default_dependency_sources()
                        txn.add_install_bundle(Gio.File.new_for_path(path), None)
                        error = self._run_transaction(txn, app, index, len(todo))
                    else:
                        txn = Flatpak.Transaction.new_for_installation(inst, None)
                        txn.add_default_dependency_sources()
                        txn.add_install(FLATHUB, self._ref(app_id), None)
                        error = self._run_transaction(txn, app, index, len(todo))
                except GLib.Error as e:
                    error = None if "already installed" in e.message.lower() else e.message
                except Exception as e:  # letöltési hiba a GitHub csomagnál
                    error = str(e)
                if error:
                    log.warning("%s: %s", app_id, error)
                    failed[app_id] = _human_error(error)
                    self._on_app_state(app_id, "failed", failed[app_id])
                else:
                    ok.append(app_id)
                    if app_id in self._bundle_tags:
                        save_bundle_version(app_id, self._bundle_tags[app_id])
                    self._on_app_state(app_id, "done", "")
        except Exception as e:
            log.error("a telepítés megszakadt: %s", e)
            for app_id in app_ids:
                if app_id not in ok and app_id not in failed:
                    failed[app_id] = _human_error(str(e))
        finally:
            for path in temp_files:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _run_transaction(self, txn, app, index, count):
        """Egy app tranzakciója (az app és a hozzá kellő összetevők). -> hibaüzenet vagy None

        A letöltött bájtok az összesítésbe mennek; az összetevőket nem nevezzük meg,
        a felületen végig az app neve látszik.
        """
        own_ref = f"app/{app['id']}/"
        state = {"ops": 1, "finished": 0, "error": None}

        def on_ready(t):
            state["ops"] = max(1, len(t.get_operations()))
            return True

        def on_new_operation(t, op, progress):
            size = op.get_download_size()

            def changed(p):
                current = p.get_bytes_transferred()
                if size:
                    current = min(current, size)  # a felmérés is ezzel a mérettel számolt
                frac = (state["finished"] + p.get_progress() / 100) / state["ops"]
                self._report(app["name"], index, count, current=current, frac=frac)

            progress.set_update_frequency(200)
            progress.connect("changed", changed)
            changed(progress)

        def on_done(t, op, commit, result):
            state["finished"] += 1
            self._progress["done"] += op.get_download_size()

        def on_error(t, op, error, details):
            state["finished"] += 1
            self._progress["done"] += op.get_download_size()
            log.warning("%s: %s", op.get_ref(), error.message)
            if op.get_ref().startswith(own_ref):
                state["error"] = error.message
            return True  # egy elhagyható kiegészítő (pl. nyelvi csomag) hibája miatt ne álljon le

        txn.connect("ready", on_ready)
        txn.connect("new-operation", on_new_operation)
        txn.connect("operation-done", on_done)
        txn.connect("operation-error", on_error)
        try:
            txn.run(None)
        except GLib.Error as e:
            return state["error"] or e.message
        return state["error"]
