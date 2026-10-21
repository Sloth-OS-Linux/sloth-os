"""A notification when a system update was prepared in the background (it installs at the next restart).

The automatic update (rpm-ostreed-automatic, "stage") downloads and prepares the new version by itself; until now
only Sloth Center showed this, so it looked as if the update came "only after a restart". It runs in the user's
session (sloth-update-notify.path / .service): when the system prepares a new version
(/run/ostree/staged-deployment), and at login. It speaks up about a version only once.
Start: python3 -m sloth_center.update_notify
"""
import json
import os
import subprocess
from pathlib import Path

from . import texts
from .i18n import tr

SEEN = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "update-notified"


def pending_deployment():
    """The version starting at the next start, if it is not the current one (a new update is waiting). Otherwise None."""
    try:
        r = subprocess.run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=60)
        deployments = json.loads(r.stdout or "{}").get("deployments", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not deployments or deployments[0].get("booted"):
        return None
    return deployments[0]


def main():
    d = pending_deployment()
    if not d:
        return 0
    key = f"{d.get('checksum')}.{d.get('serial')}"
    try:
        if SEEN.read_text().strip() == key:
            return 0
    except OSError:
        pass
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(key + "\n")
    body = tr("The new system version ({version}) has been downloaded. It will be installed at the next restart; "
              "until then you can keep working.", version=texts.version_text(d))
    try:
        r = subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=system-software-update",
                            "--expire-time=0", "--action=reboot=" + tr("Restart now"),
                            tr("An update is ready"), body], capture_output=True, text=True)
    except OSError:
        return 0
    if r.stdout.strip() == "reboot":
        subprocess.Popen(["systemctl", "reboot"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
