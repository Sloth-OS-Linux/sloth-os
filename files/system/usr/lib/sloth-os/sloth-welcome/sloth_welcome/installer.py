"""Installing apps with libflatpak, on a separate thread, with progress.

The apps are installed one by one, in the order chosen (top to bottom on the list),
each in its own transaction, together with its dependencies. Before that, a trial transaction
surveys the total download size; the UI only sees which app is being installed, and
how much of the total download is done (runtimes are not named).
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
# Most Flathub errors are temporary network problems, so we retry
MAX_ATTEMPTS = 3
# Errors travel as translation keys; the UI shows them in the chosen language
NETWORK_ERROR = "error.network"


def _human_error(raw):
    low = (raw or "").lower()
    if any(k in low for k in ("could not resolve", "network", "timed out", "timeout", "connection", "unreachable")):
        return NETWORK_ERROR
    if any(k in low for k in ("no space", "enospc")):
        return "error.disk_full"
    if any(k in low for k in ("not authorized", "authentication", "permission")):
        return "error.not_authorized"
    if "checksum" in low or "ellenőrző" in low:  # "ellenőrző": libflatpak's Hungarian message
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


# The downloaded installers of Windows programs (e.g. game launchers); after the wizard they open from here one by one
WINDOWS_INSTALLERS = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sloth-os" / "welcome-installers"


def _remote_size(url):
    """The size of the file to download (HEAD, following redirects); 0 if the server does not say."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.headers.get("Content-Length") or 0)
    except (OSError, ValueError):
        return 0


def download_windows_installer(app, on_bytes=None):
    """The official installer of the Windows program into the WINDOWS_INSTALLERS folder (written to a file, not to memory). -> path"""
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
    """The versions of the apps installed as GitHub packages: {app_id: release tag}."""
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
    """The release's Flatpak package: {name, browser_download_url, size, …} or None."""
    return next((a for a in release.get("assets", []) if a["name"].endswith(app["asset_suffix"])), None)


def download_latest_bundle(app, release=None, on_bytes=None):
    """The latest Flatpak package from the GitHub release, with an SHA256 check. -> (file, tag)"""
    name = app["name"]
    release = release or latest_release(app)
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    bundle = bundle_asset(app, release)
    bundle_name = bundle["name"] if bundle else None
    if not bundle_name or "SHA256SUMS.txt" not in assets:
        raise RuntimeError(f"{name}: no suitable package in the release")
    sums = _http_get(assets["SHA256SUMS.txt"]).decode("utf-8", "replace")
    expected = next((line.split()[0] for line in sums.splitlines()
                     if line.strip().endswith(bundle_name)), None)

    def progress(done, _total):
        if on_bytes:
            on_bytes(done)

    data = _http_get(assets[bundle_name], progress)
    if not expected or hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("checksum: the downloaded package's checksum does not match")
    fd, path = tempfile.mkstemp(suffix=".flatpak", prefix="sloth-bundle-")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path, release.get("tag_name", "")


class Installer:
    """The callbacks are called from the background thread; the caller takes care of switching threads."""

    def __init__(self, on_status, on_app_state, on_finished):
        self._on_status = on_status          # (text, details, overall 0..100 or -1)
        self._on_app_state = on_app_state    # (app_id, "installing" | "done" | "failed", hibakulcs)
        self._on_finished = on_finished      # (sikeres_idk, sikertelen {id: hibakulcs})
        self._thread = None
        self._bundle_tags = {}
        self.windows_installers = {}  # app_id -> path of the downloaded installer (they open after the wizard)
        self._progress = {"total": 0, "done": 0}  # in bytes, for all selected apps

    def start(self, app_ids):
        self._thread = threading.Thread(target=self._run, args=(list(app_ids),), daemon=True)
        self._thread.start()

    # --- Internals -------------------------------------------------------------

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
        """Status: which app is being installed ("Installing X…") and the progress bar. Download and size are not shown;
        the progress bar counts from the downloaded bytes, because that takes most of the time.

        current: the bytes of the download in progress; frac: the app's own progress 0..1
        (only counts if the total size could not be surveyed).
        """
        done = self._progress["done"] + current
        total = max(self._progress["total"], done)
        if self._progress["total"]:
            overall = int(done * 100 / total)
        else:
            overall = int((index + frac) * 100 / max(1, count))
        self._on_status(tr("install.installing", name=name), "", min(99, overall))

    def _plan(self, inst, apps, failed):
        """Surveys the total download size. -> {app_id: GitHub release} for the package apps

        The Flathub apps go into a trial transaction, which is stopped at the "ready" signal (with the sizes
        known, before downloading); so a shared runtime counts only once.
        """
        self._progress = {"total": 0, "done": 0}
        releases, total = {}, 0
        flathub = [a for a in apps if a.get("source", "flathub") == "flathub"]
        if flathub:
            sizes = {}

            def on_ready(t):
                for op in t.get_operations():
                    sizes[op.get_ref()] = op.get_download_size()
                return False  # only surveying, no installing here yet

            txn = Flatpak.Transaction.new_for_installation(inst, None)
            txn.add_default_dependency_sources()
            for app in flathub:
                try:
                    txn.add_install(FLATHUB, self._ref(app["id"]), None)
                except GLib.Error:
                    pass  # e.g. already installed; it turns out when installing
            txn.connect("ready", on_ready)
            try:
                txn.run(None)
            except GLib.Error as e:
                if not sizes:
                    log.info("surveying the size failed: %s", e.message)
            total += sum(sizes.values())
        for app in apps:
            if app.get("source") == "windows":
                total += _remote_size(app["url"])
                continue
            if app.get("source") != "github-bundle":
                continue  # "system" apps download nothing
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
            # Only apps not installed yet that failed because of a network error are retried
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
            # One by one, in the list's order: only one app is ever "being installed"
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
                        # already in the system, we only turn it on (e.g. KDE Connect: /usr/libexec/sloth-os/phone-link)
                        r = subprocess.run([app["switch"], "on"], capture_output=True, text=True, timeout=60)
                        error = None if r.returncode == 0 else (r.stderr.strip() or f"exit {r.returncode}")
                    elif app.get("source") == "github-bundle":
                        # GitHub packages go to the user, so updating them in the background needs no password
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
                except Exception as e:  # download error with the GitHub package
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
            log.error("the install was interrupted: %s", e)
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
        """One app's transaction (the app and the components it needs). -> error message or None

        The downloaded bytes go into the total; the components are not named,
        the UI shows the app's name all along.
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
                    current = min(current, size)  # the survey counted with this size too
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
            return True  # an optional extension (e.g. a language pack) failing must not stop it

        txn.connect("ready", on_ready)
        txn.connect("new-operation", on_new_operation)
        txn.connect("operation-done", on_done)
        txn.connect("operation-error", on_error)
        try:
            txn.run(None)
        except GLib.Error as e:
            return state["error"] or e.message
        return state["error"]
