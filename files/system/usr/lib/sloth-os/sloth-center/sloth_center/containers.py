"""Fejlesztői környezetek: más Linux-rendszerek dobozban (Distrobox), grafikusan.

A `distrobox create/rm/enter` és a `distrobox-export` megfelelője. A hosszú
műveletek (letöltés, első indítás) folyamatjelzővel futnak, a nyers kimenet
csak a naplóba kerül.
"""
import json
import logging
import re
import subprocess
import threading

from PySide6.QtCore import QObject, QProcess, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.containers")

# (azonosító, megjelenített név, image, csomagkezelő)
DISTROS = [
    ("ubuntu", "Ubuntu 24.04", "docker.io/library/ubuntu:24.04", "apt"),
    ("debian", "Debian 13", "docker.io/library/debian:13", "apt"),
    ("arch", "Arch Linux", "docker.io/library/archlinux:latest", "pacman"),
    ("fedora", "Fedora", "registry.fedoraproject.org/fedora-toolbox:latest", "dnf"),
]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,40}$")
PKG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")

INSTALL_CMD = {
    "apt": "sudo -n apt-get update && sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y",
    "pacman": "sudo -n pacman -Sy --noconfirm",
    "dnf": "sudo -n dnf install -y",
}


def _human_stage(line, current):
    low = line.lower()
    if "copying blob" in low or "pulling" in low or "trying to pull" in low:
        return tr("Downloading…")
    if "writing manifest" in low or "storing signatures" in low or "creating" in low:
        return tr("Creating the box…")
    if "setting up" in low or "installing" in low or "unpacking" in low or "downloading" in low:
        return tr("Installing…")
    if "container setup complete" in low or "successfully" in low:
        return tr("Almost done…")
    return current


def list_boxes():
    try:
        r = subprocess.run(["podman", "ps", "-a", "--format", "json", "--filter", "label=manager=distrobox"],
                           capture_output=True, text=True, timeout=30)
        items = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        log.warning("podman ps: %s", e)
        return []
    out = []
    for c in items:
        names = c.get("Names") or []
        image = c.get("Image", "")
        distro = next((d for d in DISTROS if d[2].split(":")[0] in image), None)
        out.append({"name": names[0] if names else c.get("Id", "")[:12],
                    "image": image,
                    "distro": distro[1] if distro else image.split("/")[-1],
                    "pm": distro[3] if distro else "",
                    "running": c.get("State") == "running"})
    return sorted(out, key=lambda b: b["name"])


class ContainersController(QObject):
    changed = Signal()
    _apps_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._boxes = []
        self._apps = []
        self._busy = False
        self._status = ""
        self._error = ""
        self._info = ""
        self._proc = None
        self._apps_ready.connect(self._on_apps)
        self.refresh()

    boxes = Property("QVariantList", lambda self: list(self._boxes), notify=changed)
    apps = Property("QVariantList", lambda self: list(self._apps), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    statusText = Property(str, lambda self: self._status, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)

    @Property("QVariantList", constant=True)
    def distros(self):
        return [{"id": d[0], "name": d[1]} for d in DISTROS]

    @Slot()
    def refresh(self):
        self._boxes = list_boxes()
        self.changed.emit()

    # --- Hosszú műveletek -----------------------------------------------------------

    def _run(self, args, status, done_text, then=None):
        if self._busy:
            return
        self._busy, self._error, self._info, self._status = True, "", "", status
        self.changed.emit()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        def read():
            for line in bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
                if line.strip():
                    log.debug("%s", line)
                    self._status = _human_stage(line, self._status)
            self.changed.emit()

        def finished(code, _st):
            self._busy = False
            if code == 0:
                self._info = done_text
                if then:
                    then()
            else:
                self._error = tr("That didn't work. Check your internet connection and try again.")
            self.refresh()

        self._proc.readyReadStandardOutput.connect(read)
        self._proc.finished.connect(finished)
        log.info("futtatás: %s", args)
        self._proc.start(args[0], args[1:])

    @Slot(str, str)
    def create(self, distro_id, name):
        name = name.strip().lower()
        distro = next((d for d in DISTROS if d[0] == distro_id), None)
        if not distro or not NAME_RE.match(name):
            self._error = tr("Enter a name in lowercase letters, without spaces (e.g. “ubuntu-box”).")
            self.changed.emit()
            return
        if any(b["name"] == name for b in self._boxes):
            self._error = tr("A box with this name already exists.")
            self.changed.emit()
            return

        def first_start():
            # Az első indítás állítja be a dobozt (felhasználó, integráció); ez is eltart egy ideig
            self._run(["distrobox", "enter", name, "--", "true"], tr("Getting ready for the first start…"),
                      tr("Done! The box “{name}” is ready to use.", name=name))

        self._run(["distrobox", "create", "--yes", "--name", name, "--image", distro[2]],
                  tr("Downloading {name}…", name=distro[1]), "", first_start)

    @Slot(str)
    def remove(self, name):
        if NAME_RE.match(name):
            self._apps = []
            self._run(["distrobox", "rm", "--force", name], tr("Deleting the box…"), tr("The box has been deleted."))

    @Slot(str)
    def openTerminal(self, name):
        if NAME_RE.match(name):
            subprocess.Popen(["konsole", "-e", "distrobox", "enter", name],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @Slot(str, str)
    def installPackage(self, name, package):
        box = next((b for b in self._boxes if b["name"] == name), None)
        pkgs = [p for p in re.split(r"[\s,]+", package.strip()) if p]
        if not box or not box["pm"] or not pkgs or not all(PKG_RE.match(p) for p in pkgs):
            self._error = tr("Enter a valid package name.")
            self.changed.emit()
            return
        cmd = f"{INSTALL_CMD[box['pm']]} {' '.join(pkgs)}"
        self._run(["distrobox", "enter", name, "--", "sh", "-c", cmd],
                  tr("Installing {packages} into the box…", packages=", ".join(pkgs)),
                  tr("Installed. If it's a graphical app, you can add it under “Apps in the Start menu”."),
                  lambda: self.listApps(name))

    @Slot(str)
    def listApps(self, name):
        """A dobozban lévő grafikus appok (exportálhatók a Start menübe)."""
        if not NAME_RE.match(name):
            return
        threading.Thread(target=self._list_apps_worker, args=(name,), daemon=True).start()

    def _on_apps(self, apps):
        self._apps = apps
        self.changed.emit()

    def _list_apps_worker(self, name):
        script = ("for f in /usr/share/applications/*.desktop; do "
                  "grep -q '^NoDisplay=true' \"$f\" && continue; "
                  "n=$(grep -m1 '^Name=' \"$f\" | cut -d= -f2-); echo \"$(basename \"$f\" .desktop)|$n\"; done")
        try:
            r = subprocess.run(["distrobox", "enter", name, "--", "sh", "-c", script],
                               capture_output=True, text=True, timeout=120)
            exported = subprocess.run(["distrobox", "enter", name, "--", "distrobox-export", "--list-apps"],
                                      capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):
            self._apps_ready.emit([])
            return
        apps = []
        for line in r.stdout.splitlines():
            if "|" in line:
                app_id, label = line.split("|", 1)
                apps.append({"box": name, "id": app_id, "name": label or app_id,
                             "exported": label in exported or app_id in exported})
        self._apps_ready.emit(apps)

    @Slot(str, str, bool)
    def setExported(self, name, app_id, exported):
        if not NAME_RE.match(name) or not re.match(r"^[A-Za-z0-9._+-]+$", app_id):
            return
        args = ["distrobox", "enter", name, "--", "distrobox-export", "--app", app_id]
        if not exported:
            args.append("--delete")
        self._run(args, tr("Updating the Start menu…"),
                  tr("Done, it's now in the Start menu.") if exported else tr("Done, removed from the Start menu."),
                  lambda: self.listApps(name))
