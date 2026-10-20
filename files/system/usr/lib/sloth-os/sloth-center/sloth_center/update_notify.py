"""Értesítés, ha a háttérben elkészült egy rendszerfrissítés (a következő újraindításkor települ).

Az automatikus frissítés (rpm-ostreed-automatic, „stage”) magától letölti és előkészíti az új verziót; eddig ezt
csak a Sloth Központ mutatta, ezért úgy tűnt, mintha a frissítés „csak újraindítás után” jönne. A felhasználó
munkamenetében fut (sloth-update-notify.path / .service): amikor a rendszer előkészít egy új verziót
(/run/ostree/staged-deployment), és bejelentkezéskor. Egy verzióról csak egyszer szól.
Indítás: python3 -m sloth_center.update_notify
"""
import json
import os
import subprocess
from pathlib import Path

from . import texts
from .i18n import tr

SEEN = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "update-notified"


def pending_deployment():
    """A következő indításkor induló verzió, ha az nem a mostani (új frissítés vár). Különben None."""
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
    body = tr("Letöltöttük az új rendszerverziót ({version}). A következő újraindításkor települ, addig nyugodtan "
              "dolgozhatsz tovább.", version=texts.version_text(d))
    try:
        r = subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=system-software-update",
                            "--expire-time=0", "--action=reboot=" + tr("Újraindítás most"),
                            tr("Elkészült egy frissítés"), body], capture_output=True, text=True)
    except OSError:
        return 0
    if r.stdout.strip() == "reboot":
        subprocess.Popen(["systemctl", "reboot"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
