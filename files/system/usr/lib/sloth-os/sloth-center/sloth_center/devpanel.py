"""Fejlesztői pult: a Sloth OS fejlesztése terminál nélkül (repó, build, aláíró kulcs, kipróbálás).

  Kapcsolat   a GitHub-repó és egy token (a jelszótárolóban: secret-tool / KWallet; ha az nincs, egy csak a
              felhasználó által olvasható fájlban). A tokent egy gomb a GitHubon, előre kitöltött jogokkal hozza létre.
  Buildek     a legutóbbi futások (GitHub Actions), új build indítása (image vagy ISO), havi Actions-percek.
  Aláíró kulcs  be van-e állítva a SIGNING_SECRET; új kulcspár a cosign-nal (Podman-konténerben, mert a cosign
              nincs az image-ben): a nyilvános kulcsot a pult commitolja, a titkosat a vágólapra teszi, és megnyitja
              a GitHub titok-oldalát (a titok feltöltéséhez titkosítás kellene, amihez nincs könyvtár a rendszerben).
  Kipróbálás  bejelentkezés a csomagtárolóba (privát repónál kell, sloth-helper registry-login), átállás egy
              buildre (rpm-ostree rebase), vissza a legfrissebbre; virtuális gép (GNOME Boxes).
"""
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .i18n import tr

log = logging.getLogger("sloth-center.devpanel")

HELPER = "/usr/libexec/sloth-os/sloth-helper"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "devpanel.json"
TOKEN_FILE = CONFIG.with_name("devpanel-token")
API = "https://api.github.com"
DEFAULT_REPO = "Sloth-OS-Linux/sloth-os"
REPO_RE = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{20,255}$")
# A token létrehozása: classic token, előre kitöltött jogokkal (repó, workflow, csomagok olvasása)
TOKEN_URL = ("https://github.com/settings/tokens/new?scopes=repo,workflow,read:packages"
             "&description=Sloth%20OS%20fejleszt%C5%91i%20pult")
COSIGN_IMAGE = "gcr.io/projectsigstore/cosign:v2.4.1"
WORKFLOWS = {"image": "build.yml", "iso": "iso.yml"}


# --- Token tárolása ------------------------------------------------------------------------------------

def _secret_tool(*args, stdin=None):
    return subprocess.run(["secret-tool", *args], input=stdin, capture_output=True, text=True, timeout=15)


def load_token():
    if shutil.which("secret-tool"):
        try:
            r = _secret_tool("lookup", "service", "sloth-os-devpanel")
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_token(token):
    """A jelszótárolóba; ha az nem elérhető, egy csak a felhasználó által olvasható fájlba."""
    if shutil.which("secret-tool"):
        try:
            r = _secret_tool("store", "--label=Sloth OS fejlesztői pult", "service", "sloth-os-devpanel",
                             stdin=token)
            if r.returncode == 0:
                TOKEN_FILE.unlink(missing_ok=True)
                return
        except (OSError, subprocess.SubprocessError):
            pass
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)


def forget_token():
    if shutil.which("secret-tool"):
        try:
            _secret_tool("clear", "service", "sloth-os-devpanel")
        except (OSError, subprocess.SubprocessError):
            pass
    TOKEN_FILE.unlink(missing_ok=True)


# --- GitHub API --------------------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status, message=""):
        super().__init__(message or str(status))
        self.status = status


def api(token, method, path, body=None, timeout=20):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                                          "Authorization": f"Bearer {token}", "User-Agent": "sloth-center"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as e:
        raise ApiError(e.code) from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ApiError(0, str(e)) from e


def _when(iso):
    try:
        t = time.mktime(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
        return time.strftime("%m.%d. %H:%M", time.localtime(t))
    except (ValueError, TypeError):
        return ""


def run_state(run):
    """Egy futás állapota: "running" | "ok" | "failed" | "cancelled"."""
    if run.get("status") != "completed":
        return "running"
    return {"success": "ok", "cancelled": "cancelled", "skipped": "cancelled"}.get(run.get("conclusion"), "failed")


def actions_minutes(token, owner):
    """Az e havi Actions-percek (az új számlázási API-ból), vagy None, ha a token / fiók nem engedi."""
    data = None
    for path in (f"/organizations/{owner}/settings/billing/usage", f"/users/{owner}/settings/billing/usage"):
        try:
            data = api(token, "GET", path)
            break
        except ApiError:
            pass
    if data is None:
        return None
    month = time.strftime("%Y-%m")
    items = [i for i in data.get("usageItems", []) if i.get("product") == "actions"
             and str(i.get("unitType", "")).lower() == "minutes" and str(i.get("date", "")).startswith(month)]
    return round(sum(float(i.get("quantity") or 0) for i in items)) if items else None


class DevPanelController(QObject):
    changed = Signal()
    _loaded = Signal(object)
    _done = Signal(str, str)  # (üzenet, hiba)

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = self._config()
        self._repo = cfg.get("repo") or DEFAULT_REPO
        self._token = load_token()
        self._runs = []
        self._minutes = -1
        self._has_secret = None
        self._private = None
        self._busy = False
        self._message = ""
        self._error = ""
        self._image = ""
        self._ostree = None
        self._loaded.connect(self._on_loaded)
        self._done.connect(self._on_done)
        if self._token:
            self.refresh()

    # --- Tulajdonságok -------------------------------------------------------------------------------

    repo = Property(str, lambda self: self._repo, notify=changed)
    connected = Property(bool, lambda self: bool(self._token), notify=changed)
    runs = Property("QVariantList", lambda self: list(self._runs), notify=changed)
    minutes = Property(int, lambda self: self._minutes, notify=changed)
    hasSecret = Property(bool, lambda self: bool(self._has_secret), notify=changed)
    secretKnown = Property(bool, lambda self: self._has_secret is not None, notify=changed)
    privateRepo = Property(bool, lambda self: bool(self._private), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    currentImage = Property(str, lambda self: self._booted_image(), notify=changed)

    @staticmethod
    def _config():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_config(self):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"repo": self._repo}, indent=2), encoding="utf-8")

    def _background(self, work):
        """Hálózati művelet háttérszálon; a végén üzenet (vagy hiba) és frissítés."""
        self._busy, self._message, self._error = True, "", ""
        self.changed.emit()

        def run():
            try:
                self._done.emit(work() or "", "")
            except ApiError as e:
                self._done.emit("", self._api_error(e))
            except Exception as e:  # a felület ne akadjon meg
                log.warning("fejlesztői pult: %s", e)
                self._done.emit("", tr("That didn't work. Please try again later."))

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, message, error):
        self._busy, self._message, self._error = False, message, error
        if message == "key-ready":
            self._on_key_ready()  # a vágólap csak a fő szálon írható
        self.changed.emit()
        if not error:
            self.refresh()

    @staticmethod
    def _api_error(e):
        if e.status == 401:
            return tr("GitHub didn't accept the token. Create a new one and enter it here.")
        if e.status in (403, 404):
            return tr("The token has no access to this repository (needed: repo, workflow, read:packages), or the repository name is wrong.")
        if e.status == 0:
            return tr("No connection to GitHub. Check your internet connection.")
        return tr("GitHub reported an error ({code}). Please try again later.", code=e.status)

    # --- Kapcsolat -------------------------------------------------------------------------------------

    @Slot()
    def createToken(self):
        subprocess.Popen(["xdg-open", TOKEN_URL], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str, str)
    def connectRepo(self, repo, token):
        repo, token = repo.strip(), token.strip()
        if not REPO_RE.match(repo):
            self._error = tr("The repository name has the form “owner/name”, for example Sloth-OS-Linux/sloth-os.")
            self.changed.emit()
            return
        if token and not TOKEN_RE.match(token):
            self._error = tr("That doesn't look like a GitHub token. Copy it in again.")
            self.changed.emit()
            return
        token = token or self._token

        def work():
            info = api(token, "GET", f"/repos/{repo}")
            save_token(token)
            self._token, self._repo, self._private = token, repo, bool(info.get("private"))
            self._save_config()
            return tr("Connected: {repo}", repo=repo)

        self._background(work)

    @Slot()
    def disconnect(self):
        forget_token()
        self._token, self._runs, self._has_secret, self._minutes = "", [], None, -1
        self._message = tr("The token has been removed from this computer.")
        self.changed.emit()

    # --- Buildek --------------------------------------------------------------------------------------

    @Slot()
    def refresh(self):
        if not self._token:
            return
        token, repo = self._token, self._repo

        def work():
            out = {}
            try:
                runs = api(token, "GET", f"/repos/{repo}/actions/runs?per_page=12").get("workflow_runs", [])
                out["runs"] = [{"id": r["id"], "name": r.get("name", ""), "title": r.get("display_title", ""),
                                "sha": (r.get("head_sha") or "")[:7], "branch": r.get("head_branch", ""),
                                "state": run_state(r), "when": _when(r.get("created_at", "")),
                                "url": r.get("html_url", "")} for r in runs]
                secrets = api(token, "GET", f"/repos/{repo}/actions/secrets").get("secrets", [])
                out["secret"] = any(s.get("name") == "SIGNING_SECRET" for s in secrets)
                out["private"] = bool(api(token, "GET", f"/repos/{repo}").get("private"))
                out["minutes"] = actions_minutes(token, repo.split("/")[0])
            except ApiError as e:
                out["error"] = self._api_error(e)
            self._loaded.emit(out)

        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, out):
        self._runs = out.get("runs", self._runs)
        self._has_secret = out.get("secret", self._has_secret)
        self._private = out.get("private", self._private)
        m = out.get("minutes")
        self._minutes = -1 if m is None else int(m)
        if out.get("error"):
            self._error = out["error"]
        self.changed.emit()

    @Slot(str)
    def startBuild(self, kind):
        workflow = WORKFLOWS.get(kind)
        if not workflow or not self._token:
            return
        token, repo = self._token, self._repo

        def work():
            api(token, "POST", f"/repos/{repo}/actions/workflows/{workflow}/dispatches", {"ref": "main"})
            return tr("Started. It will show up in the list in a few seconds.")

        self._background(work)

    @Slot(str)
    def openUrl(self, url):
        if url.startswith("https://github.com/"):
            subprocess.Popen(["xdg-open", url], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- Aláíró kulcs ---------------------------------------------------------------------------------

    @Slot()
    def createSigningKey(self):
        """Új cosign kulcspár (Podmanben): a nyilvánosat commitoljuk, a titkosat a vágólapra tesszük."""
        if not self._token:
            return
        token, repo = self._token, self._repo

        def work():
            with tempfile.TemporaryDirectory() as tmp:
                r = subprocess.run(["podman", "run", "--rm", "--cgroups=disabled", "-e", "COSIGN_PASSWORD=",
                                    "-v", f"{tmp}:/work:Z", "-w", "/work", COSIGN_IMAGE, "generate-key-pair"],
                                   capture_output=True, text=True, timeout=600)
                if r.returncode != 0:
                    log.warning("cosign: %s", r.stderr[-2000:])
                    raise RuntimeError("cosign")
                pub = Path(tmp, "cosign.pub").read_text(encoding="utf-8")
                key = Path(tmp, "cosign.key").read_text(encoding="utf-8")
            try:
                sha = api(token, "GET", f"/repos/{repo}/contents/cosign.pub").get("sha")
            except ApiError as e:
                if e.status != 404:
                    raise
                sha = None
            body = {"message": "Új aláíró kulcs (a fejlesztői pultból)",
                    "content": base64.b64encode(pub.encode()).decode()}
            if sha:
                body["sha"] = sha
            api(token, "PUT", f"/repos/{repo}/contents/cosign.pub", body)
            self._clipboard = key
            return "key-ready"

        self._background(work)

    def _on_key_ready(self):
        QGuiApplication.clipboard().setText(getattr(self, "_clipboard", ""))
        self._clipboard = ""
        self.openUrl(f"https://github.com/{self._repo}/settings/secrets/actions/new")
        self._message = tr("The public key has been added to the repository. The private key is on the clipboard: on "
                           "the GitHub page that just opened, set the name to SIGNING_SECRET, paste it into the value"
                           " (Ctrl+V), then click “Add secret”. Afterwards, copy something else to overwrite the "
                           "clipboard.")
        self.changed.emit()

    # --- Kipróbálás ---------------------------------------------------------------------------------

    def _booted_image(self):
        if self._image:
            return self._image
        try:
            if self._ostree is None:
                from .rpmostree import RpmOstree
                self._ostree = RpmOstree()
            booted = self._ostree.booted()
            self._image = str(booted.get("container-image-reference") or "")
        except Exception as e:  # nincs rpm-ostree (pl. fejlesztői gépen)
            log.info("rpm-ostree: %s", e)
        return self._image

    @Slot()
    def registryLogin(self):
        """A privát csomagtároló a rendszer frissítéseihez és az image-váltáshoz (rendszergazdai jóváhagyással)."""
        if not self._token:
            return
        owner = self._repo.split("/")[0]

        def work():
            r = subprocess.run(["pkexec", HELPER, "registry-login", "ghcr.io", owner], input=self._token + "\n",
                               capture_output=True, text=True, timeout=120)
            try:
                ok = json.loads(r.stdout or "{}").get("ok")
            except ValueError:
                ok = False
            if not ok:
                raise RuntimeError("registry-login")
            return tr("Done: this computer can now reach the private package registry.")

        self._background(work)

    @Slot(str)
    def switchTo(self, tag):
        """Átállás egy buildre (a következő újraindításkor indul); tag: pl. "a1b2c3d-44" vagy "latest"."""
        image = self._booted_image()
        if not image or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", tag):
            self._error = tr("We can't tell which image this computer is running.")
            self.changed.emit()
            return
        target = re.sub(r":[^:/]+$", f":{tag}", image)
        self._busy, self._message, self._error = True, tr("Downloading the new edition…"), ""
        self.changed.emit()

        def on_finished(ok, raw):
            self._busy = False
            if ok:
                self._message = tr("Done. Restart the computer and this version will start. The old one stays in the boot menu.")
            else:
                log.warning("rebase: %s", raw)
                self._error = tr("Switching didn't work. For a private repository, sign in to the package registry first.")
            self.changed.emit()

        try:
            from .rpmostree import Transaction
            self._ostree.rebase(target, lambda address: Transaction(address, lambda t: None, lambda p: None,
                                                                    lambda t, r: None, on_finished),
                                lambda raw: on_finished(False, raw))
        except Exception as e:
            on_finished(False, str(e))

    @Slot(str, result=str)
    def tagFor(self, sha):
        """Segéd a QML-nek: a build image-címkéje (a BlueBuild így címkéz: <commit>-<Fedora-verzió>)."""
        return f"{sha}-{fedora_version()}"

    @Slot()
    def openBoxes(self):
        """Virtuális gép: GNOME Boxes (ha nincs telepítve, a Discoverben)."""
        r = subprocess.run(["flatpak", "info", "org.gnome.Boxes"], capture_output=True)
        cmd = (["flatpak", "run", "org.gnome.Boxes"] if r.returncode == 0
               else ["plasma-discover", "appstream://org.gnome.Boxes"])
        subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fedora_version():
    try:
        for line in Path("/usr/lib/os-release").read_text().splitlines():
            if line.startswith("VERSION_ID="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return "44"
