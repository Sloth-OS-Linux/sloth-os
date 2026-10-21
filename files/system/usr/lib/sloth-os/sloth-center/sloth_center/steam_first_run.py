"""A notification about Steam's first start.

On its first start Steam downloads its own client without a window (hundreds of MB), and only opens
afterwards; until then it looks as if it had not started at all. Then a Plasma notification
says what is happening and how much it has downloaded so far; when Steam's window appears,
the notification disappears. If Steam opens quickly, we say nothing.

It runs in the user's session (sloth-steam-first-run.path / .service), when Steam's
data folder is created, and at login; once it has gone through, it exits right away.
Start: python3 -m sloth_center.steam_first_run
"""
import os
import subprocess
import time
from pathlib import Path

from .i18n import tr

STEAM_DATA = Path.home() / ".var/app/com.valvesoftware.Steam"
DONE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "steam-first-run.done"
# Steam's processes (/proc/<pid>/comm cuts the name to 15 characters)
STEAM_PROCS = {"steam", "steam.sh", "steam-wrapper", "steamwebhelper"}
# Steam's interface appears with this process: if it runs, the download is done
UI_PROC = "steamwebhelper"
# If Steam opens within this time, no notification is needed
QUIET_S = 15
POLL_S = 3
MB = 1024 * 1024


def processes():
    names = set()
    uid = os.getuid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != uid:
                continue
            with open(f"/proc/{pid}/comm", encoding="utf-8", errors="replace") as f:
                names.add(f.read().strip())
        except OSError:
            continue
    return names


def data_size():
    total = 0
    for root, _dirs, files in os.walk(STEAM_DATA):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def notify(body, replace_id=None):
    args = ["notify-send", "--app-name=Sloth OS", "--icon=com.valvesoftware.Steam", "--expire-time=0",
            "--print-id"]
    if replace_id:
        args.append(f"--replace-id={replace_id}")
    try:
        out = subprocess.run([*args, tr("Starting Steam for the first time"), body],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return replace_id
    return out if out.isdigit() else replace_id


def close(notification_id):
    try:
        subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                        "--object-path", "/org/freedesktop/Notifications",
                        "--method", "org.freedesktop.Notifications.CloseNotification", notification_id],
                       capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def mark_done():
    DONE.parent.mkdir(parents=True, exist_ok=True)
    DONE.touch()


def main():
    if DONE.exists():
        return 0
    # We wait until the user starts Steam (something else may create the folder before)
    while not processes() & STEAM_PROCS:
        time.sleep(POLL_S)
    started, start_size = time.monotonic(), data_size()
    notification = None
    gone = 0
    while True:
        procs = processes()
        if UI_PROC in procs:
            mark_done()
            break
        # If Steam exited meanwhile (e.g. the user stopped it), we watch again next time
        gone = gone + 1 if not procs & STEAM_PROCS else 0
        if gone >= 3:
            break
        if time.monotonic() - started >= QUIET_S:
            mb = max(0, data_size() - start_size) // MB
            body = tr("Steam is downloading its own updates. This can take a few minutes, then it will open by itself.")
            if mb:
                body += "\n" + tr("{mb} MB downloaded", mb=mb)
            notification = notify(body, notification)
        time.sleep(POLL_S)
    if notification:
        close(notification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
