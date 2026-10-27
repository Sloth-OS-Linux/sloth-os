"""A notification when the NVIDIA version is ready (the system side: /usr/libexec/sloth-os/nvidia-auto).

It runs in the user's session (sloth-nvidia-notify.path / .service): when the state file changes and
at login. It speaks up about a state only once. Start: python3 -m sloth_center.nvidia_notify
"""
import os
import subprocess
from pathlib import Path

from sloth_common import quiet_hours

from .i18n import tr

STATE = Path("/var/lib/sloth-os/nvidia-auto")
SEEN = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "nvidia-notified"


def main():
    try:
        state = STATE.read_text().strip()
    except OSError:
        return 0
    if state not in ("ready", "ready-mok"):
        return 0  # we do not disturb while downloading or on error (it tries again in the background)
    try:
        if SEEN.read_text().strip() == state:
            return 0
    except OSError:
        pass
    # quiet hours (Sloth Center → Updates): not now, it comes again when they end
    if quiet_hours.defer("sloth_center.nvidia_notify"):
        return 0
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(state + "\n")
    if state == "ready":
        body = tr("The driver for your NVIDIA graphics card is ready. After a restart it runs at full power.")
        actions = ["--action=reboot=" + tr("Restart now")]
    else:
        body = tr("The driver for your NVIDIA graphics card is ready. When you restart, the computer asks for "
                  "confirmation on a blue screen: Sloth Center shows you step by step what to do there.")
        actions = ["--action=guide=" + tr("Open guide")]
    try:
        r = subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=preferences-devices-cpu",
                            "--expire-time=0", *actions, tr("NVIDIA driver"), body],
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
