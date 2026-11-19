"""Restore points (Sloth Center → Updates): before a bigger change the system version that runs now is kept and the
home folders are backed up; going back brings both back.

Made by root (/usr/libexec/sloth-os/restore-points through sloth-helper-backup, no password, like "Back up now"):
  - automatically before an NVIDIA driver switch (drivers.py, nvidia-auto), a kernel parameter or a system package
    (advanced.py), loading a settings file (settings_backup.py) and a taskbar layout change (appearance.py):
    before_change(reason, then);
  - by hand: "Create a restore point".
Going back to one:
  - the system version, if another one runs now: set as the default for the next start (sloth-helper-versions
    set-default, with the password, as choosing a version on this page);
  - the settings (the desktop's and the apps': ~/.config and KDE's own data in ~/.local/share, SETTINGS), at the
    next sign-in, before Plasma starts (sloth-restore-settings.service runs apply_pending()), because a running
    desktop writes its settings back when it ends. The settings in use until then are put aside first
    (~/.local/share/sloth-os/before-restore/<time>), so going back can be undone. Files (documents, pictures…) are
    never touched.
"""
import datetime
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from sloth_common import snapshots as snap

log = logging.getLogger("sloth-center.restore-points")

HELPER_BACKUP = "/usr/libexec/sloth-os/sloth-helper-backup"
HELPER_VERSIONS = "/usr/libexec/sloth-os/sloth-helper-versions"
STATE = Path("/var/lib/sloth-os/restore-points.json")
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
PENDING = STATE_HOME / "sloth-os" / "restore-settings.json"
ASIDE = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "sloth-os" / "before-restore"
KEEP_ASIDE = 2
# The settings a restore point brings back (relative to the home folder): every app's settings, and the desktop's
# own data that is not in ~/.config (the panels, the window rules, the screens, the activities, the user's own Start
# menu entries). Not: documents and other files, browsers' profiles (~/.mozilla, ~/.var), the password store.
SETTINGS = (".config", ".local/share/plasma", ".local/share/kwin", ".local/share/kscreen",
            ".local/share/kactivitymanagerd", ".local/share/konsole", ".local/share/dolphin",
            ".local/share/applications", ".local/share/kxmlgui5")


def N_(text):
    return text


REASON_TEXTS = {
    "driver": N_("Before changing the graphics driver"),
    "kernel-args": N_("Before changing a kernel parameter"),
    "packages": N_("Before changing system packages"),
    "settings-file": N_("Before loading settings from a file"),
    "layout": N_("Before changing the taskbar layout"),
    "manual": N_("Made by hand"),
}


def load(path=None):
    try:
        data = json.loads(Path(path or STATE).read_text())
        return [p for p in data.get("points", []) if isinstance(p, dict) and p.get("id")]
    except (OSError, ValueError, AttributeError):
        return []


def booted_checksum():
    try:
        out = subprocess.run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=60).stdout
        deploys = json.loads(out or "{}").get("deployments", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return "", []
    booted = next((d.get("checksum", "") for d in deploys if d.get("booted")), "")
    return booted, [d.get("checksum", "") for d in deploys]


def own_home_rel():
    rel, _problem = snap.locate(Path.home())
    return rel


def settings_source(point, home_rel=None):
    """The point's copy of this user's home folder, if its snapshot has it. -> Path or None"""
    home_rel = own_home_rel() if home_rel is None else home_rel
    if not point.get("snapshot") or home_rel is None:
        return None
    src = snap.SNAP_DIR / point["snapshot"] / home_rel
    return src if (src / ".config").is_dir() else None


def describe(points, booted, deploys, home_rel=None):
    """The points as the page shows them: [{id, when (timestamp), reason, system ("same" | "earlier" | "gone"),
    settings (bool)}], the newest first."""
    out = []
    for p in points:
        try:
            when = datetime.datetime.fromisoformat(p["when"])
        except (KeyError, ValueError):
            continue
        checksum = p.get("checksum", "")
        system = "same" if checksum == booted else "earlier" if checksum in deploys else "gone"
        out.append({"id": p["id"], "when": when.timestamp(), "reason": p.get("reason", "manual"), "system": system,
                    "settings": settings_source(p, home_rel) is not None})
    return out


def create(reason):
    """Makes a restore point (root, without a password). -> True if it was made"""
    try:
        r = subprocess.run(["pkexec", HELPER_BACKUP, "restore-point", reason], capture_output=True, text=True,
                           timeout=900)
        return bool(json.loads(r.stdout.strip().splitlines()[-1]).get("ok"))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as e:
        log.warning("restore point (%s): %s", reason, e)
        return False


def delete(point_id):
    try:
        r = subprocess.run(["pkexec", HELPER_BACKUP, "restore-point-delete", point_id], capture_output=True,
                           text=True, timeout=300)
        return bool(json.loads(r.stdout.strip().splitlines()[-1]).get("ok"))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return False


_runner = None


def before_change(reason, then):
    """Makes a restore point in the background, then runs `then` on the GUI thread (the change itself), whether the
    point could be made or not (a computer without Btrfs still gets the system part, or nothing)."""
    global _runner
    from PySide6.QtCore import QObject, Signal

    class Runner(QObject):
        ready = Signal(object)

    if _runner is None:
        _runner = Runner()
        _runner.ready.connect(lambda fn: fn())

    def work():
        create(reason)
        _runner.ready.emit(then)

    threading.Thread(target=work, daemon=True).start()


# --- Settings back, at the next sign-in ------------------------------------------------------------------------

def schedule_settings(point):
    """Marks the point's settings to come back at the next sign-in. -> True if the point has them"""
    src = settings_source(point)
    if src is None:
        return False
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps({"id": point["id"], "source": str(src)}))
    return True


def cancel_settings():
    PENDING.unlink(missing_ok=True)


def pending():
    try:
        return json.loads(PENDING.read_text())
    except (OSError, ValueError):
        return None


def _copy(src, dst):
    """A copy of a folder (reflinks on Btrfs: instant, no new space). -> True if it worked"""
    r = subprocess.run(["cp", "-a", "--reflink=auto", "--", str(src), str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        log.warning("copy %s: %s", src, r.stderr.strip())
    return r.returncode == 0


def apply_pending(home=None, now=None):
    """Brings the marked settings back (sloth-restore-settings.service, before Plasma starts). The settings in use
    are put aside first; if a copy fails, what was put aside goes back. -> (restored, failed) counts"""
    job = pending()
    if not job:
        return 0, 0
    PENDING.unlink(missing_ok=True)          # once, even if it fails: never a loop at every sign-in
    home = Path(home or Path.home())
    src = Path(job.get("source", ""))
    if not (src / ".config").is_dir():
        log.warning("restore point %s: its settings are gone", job.get("id"))
        return 0, 1
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d %H.%M.%S")
    aside = ASIDE / stamp
    restored = failed = 0
    for rel in SETTINGS:
        old = src / rel
        if not old.exists():
            continue                          # not there at the point: what is here now stays
        current = home / rel
        target_aside = aside / rel
        if current.exists() or current.is_symlink():
            target_aside.parent.mkdir(parents=True, exist_ok=True)
            os.rename(current, target_aside)
        current.parent.mkdir(parents=True, exist_ok=True)
        if _copy(old, current):
            restored += 1
        else:
            failed += 1
            shutil.rmtree(current, ignore_errors=True)
            if target_aside.exists():
                os.rename(target_aside, current)
    # only the newest few sets of put-aside settings are kept
    if ASIDE.is_dir():
        for old_set in sorted(ASIDE.iterdir())[:-KEEP_ASIDE]:
            shutil.rmtree(old_set, ignore_errors=True)
    log.info("restore point %s: %d restored, %d failed, the earlier settings in %s", job.get("id"), restored,
             failed, aside)
    return restored, failed


def main():
    """sloth-restore-settings.service: the settings of a restore point back, before the desktop starts."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    restored, failed = apply_pending()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
