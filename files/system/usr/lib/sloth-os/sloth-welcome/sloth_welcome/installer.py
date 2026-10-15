"""Appok telepítése a libflatpak-kal, külön szálon, folyamatjelzéssel.

Egy tranzakcióban megy minden kiválasztott app (így legfeljebb egyszer kell
jóváhagyni), a függőségekkel együtt. A felület csak emberi nyelvű állapotot kap.
"""
import hashlib
import json
import logging
import os
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


def download_latest_bundle(app, on_status=lambda *a: None, release=None):
    """Legfrissebb Flatpak csomag a GitHub kiadásból, SHA256 ellenőrzéssel. -> (fájl, címke)"""
    name = app["name"]
    on_status(tr("install.downloading", name=name), "", -1)
    release = release or latest_release(app)
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    bundle_name = next((n for n in assets if n.endswith(app["asset_suffix"])), None)
    if not bundle_name or "SHA256SUMS.txt" not in assets:
        raise RuntimeError(f"{name}: nincs megfelelő csomag a kiadásban")
    sums = _http_get(assets["SHA256SUMS.txt"]).decode("utf-8", "replace")
    expected = next((line.split()[0] for line in sums.splitlines()
                     if line.strip().endswith(bundle_name)), None)

    def progress(done, total):
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

    def _download_bundle(self, app):
        path, tag = download_latest_bundle(app, self._on_status)
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
            txn = Flatpak.Transaction.new_for_installation(inst, None)
            txn.add_default_dependency_sources()
            # A GitHub-csomagok a felhasználóhoz kerülnek, így a háttérfrissítésükhöz nem kell jelszó
            user_inst = Flatpak.Installation.new_user(None)
            user_txn = None
            wanted, user_wanted = {}, {}
            for app_id in app_ids:
                app = catalog.find_app(app_id)
                if not app:
                    continue
                try:
                    if app.get("source") == "github-bundle":
                        path = self._download_bundle(app)
                        temp_files.append(path)
                        if user_txn is None:
                            self._ensure_flathub(user_inst)
                            user_txn = Flatpak.Transaction.new_for_installation(user_inst, None)
                            user_txn.add_default_dependency_sources()
                        user_txn.add_install_bundle(Gio.File.new_for_path(path), None)
                        user_wanted[app_id] = app
                    else:
                        txn.add_install(FLATHUB, f"app/{app_id}/{Flatpak.get_default_arch()}/stable", None)
                        wanted[app_id] = app
                except GLib.Error as e:
                    if "already installed" in e.message.lower():
                        ok.append(app_id)
                        self._on_app_state(app_id, "done", "")
                    else:
                        log.warning("%s: %s", app_id, e.message)
                        failed[app_id] = _human_error(e.message)
                        self._on_app_state(app_id, "failed", failed[app_id])
                except Exception as e:  # letöltési hiba a GitHub csomagnál
                    log.warning("%s: %s", app_id, e)
                    failed[app_id] = _human_error(str(e))
                    self._on_app_state(app_id, "failed", failed[app_id])

            if wanted:
                self._run_transaction(txn, wanted, ok, failed)
            if user_wanted:
                self._run_transaction(user_txn, user_wanted, ok, failed)
                for app_id in user_wanted:
                    if app_id in ok and app_id in self._bundle_tags:
                        save_bundle_version(app_id, self._bundle_tags[app_id])
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

    def _run_transaction(self, txn, wanted, ok, failed):
        # Az összesített folyamat a letöltendő méret szerint halad (egy nyelvi csomag ne számítson
        # annyit, mint egy 1 GB-os futtatókörnyezet); ha a méret nem ismert, műveletenként egyenlően
        state = {"weights": {}, "total": 1, "done": 0}

        def app_of(op):
            parts = op.get_ref().split("/")
            return parts[1] if len(parts) > 1 and parts[0] == "app" and parts[1] in wanted else None

        def owner_of(op, seen=None):
            """Melyik kiválasztott apphoz kell ez a művelet (a futtatókörnyezet, a kiegészítők is)."""
            app_id = app_of(op)
            if app_id:
                return app_id
            seen = seen or set()
            for rel in op.get_related_to_ops() or []:
                if id(rel) not in seen:
                    seen.add(id(rel))
                    found = owner_of(rel, seen)
                    if found:
                        return found
            return None

        def weight(op):
            return state["weights"].get(op.get_ref(), 1)

        def on_ready(t):
            ops = t.get_operations()
            sizes = {op.get_ref(): op.get_download_size() for op in ops}
            if all(sizes.values()):
                state["weights"] = sizes
            state["total"] = max(1, sum(weight(op) for op in ops))
            return True

        def on_new_operation(t, op, progress):
            app_id = app_of(op)
            if app_id:
                self._on_app_state(app_id, "installing", "")
            owner = owner_of(op)
            name = wanted[owner]["name"] if owner else None
            size_mb = op.get_download_size() // (1024 * 1024)

            def changed(p):
                pct = p.get_progress()
                overall = int((state["done"] + weight(op) * pct / 100) * 100 / state["total"])
                if pct < 100:
                    # Letöltés: mit és mennyit
                    text = tr("install.downloading", name=name) if name else tr("install.runtime")
                    mb = p.get_bytes_transferred() // (1024 * 1024)
                    if size_mb:
                        detail = f"{tr('install.mb', mb=min(mb, size_mb))} / {tr('install.mb', mb=size_mb)}"
                    else:
                        detail = tr("install.mb_downloaded", mb=mb) if mb else ""
                else:
                    # A letöltés kész, a fájlok a helyükre kerülnek
                    text = tr("install.installing", name=name) if name else tr("install.runtime")
                    detail = ""
                self._on_status(text, detail, min(99, overall))

            progress.set_update_frequency(200)
            progress.connect("changed", changed)
            changed(progress)

        def on_done(t, op, commit, result):
            state["done"] += weight(op)
            app_id = app_of(op)
            if app_id:
                ok.append(app_id)
                self._on_app_state(app_id, "done", "")

        def on_error(t, op, error, details):
            state["done"] += weight(op)
            app_id = app_of(op)
            log.warning("%s: %s", op.get_ref(), error.message)
            if app_id:
                failed[app_id] = _human_error(error.message)
                self._on_app_state(app_id, "failed", failed[app_id])
            return True  # a többi app telepítése menjen tovább

        txn.connect("ready", on_ready)
        txn.connect("new-operation", on_new_operation)
        txn.connect("operation-done", on_done)
        txn.connect("operation-error", on_error)
        try:
            txn.run(None)
        except GLib.Error as e:
            log.warning("tranzakció: %s", e.message)
            for app_id in wanted:
                if app_id not in ok and app_id not in failed:
                    failed[app_id] = _human_error(e.message)
                    self._on_app_state(app_id, "failed", failed[app_id])
