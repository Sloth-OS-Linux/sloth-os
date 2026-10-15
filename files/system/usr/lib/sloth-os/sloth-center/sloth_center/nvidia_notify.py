"""Értesítés, ha az NVIDIA-s változat elkészült (a rendszer oldalt: /usr/libexec/sloth-os/nvidia-auto).

A felhasználó munkamenetében fut (sloth-nvidia-notify.path / .service): az állapotfájl változásakor és
bejelentkezéskor. Egy állapotról csak egyszer szól. Indítás: python3 -m sloth_center.nvidia_notify
"""
import os
import subprocess
from pathlib import Path

from .i18n import tr

STATE = Path("/var/lib/sloth-os/nvidia-auto")
SEEN = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "nvidia-notified"


def main():
    try:
        state = STATE.read_text().strip()
    except OSError:
        return 0
    if state not in ("ready", "ready-mok"):
        return 0  # letöltés közben és hiba esetén nem zavarjuk (a háttérben újra próbálja)
    try:
        if SEEN.read_text().strip() == state:
            return 0
    except OSError:
        pass
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(state + "\n")
    if state == "ready":
        body = tr("Az NVIDIA videókártyád illesztőprogramja elkészült. Újraindítás után teljes erővel működik.")
        actions = ["--action=reboot=" + tr("Újraindítás most")]
    else:
        body = tr("Az NVIDIA videókártyád illesztőprogramja elkészült. Újraindításkor a gép egy kék képernyőn "
                  "megerősítést kér: a Sloth Központ lépésről lépésre megmutatja, mit kell ott tenni.")
        actions = ["--action=guide=" + tr("Útmutató megnyitása")]
    try:
        r = subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=preferences-devices-cpu",
                            "--expire-time=0", *actions, tr("NVIDIA illesztőprogram"), body],
                           capture_output=True, text=True)
    except OSError:
        return 0
    choice = r.stdout.strip()
    if choice == "reboot":
        subprocess.Popen(["systemctl", "reboot"])
    elif choice == "guide":
        subprocess.Popen(["sloth-center", "--page", "drivers"], start_new_session=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
