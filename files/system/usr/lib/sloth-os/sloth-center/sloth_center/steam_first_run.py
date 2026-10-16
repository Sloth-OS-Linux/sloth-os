"""Értesítés a Steam első indításáról.

Első indításkor a Steam ablak nélkül letölti a saját kliensét (több száz MB), és csak utána
nyílik meg; addig úgy tűnik, mintha el sem indult volna. Ilyenkor egy Plasma-értesítés
mondja meg, mi történik, és mennyit töltött le eddig; amikor a Steam ablaka megjelenik,
az értesítés eltűnik. Ha a Steam gyorsan megnyílik, nem szólunk.

A felhasználó munkamenetében fut (sloth-steam-first-run.path / .service), amikor a Steam
adatmappája létrejön, és bejelentkezéskor; ha egyszer már végigment, rögtön kilép.
Indítás: python3 -m sloth_center.steam_first_run
"""
import os
import subprocess
import time
from pathlib import Path

from .i18n import tr

STEAM_DATA = Path.home() / ".var/app/com.valvesoftware.Steam"
DONE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "steam-first-run.done"
# A Steam folyamatai (a /proc/<pid>/comm 15 karakterre vágja a nevet)
STEAM_PROCS = {"steam", "steam.sh", "steam-wrapper", "steamwebhelper"}
# A Steam felülete ezzel a folyamattal jelenik meg: ha fut, a letöltés kész
UI_PROC = "steamwebhelper"
# Ha a Steam ennyi idő alatt megnyílik, nem kell értesítés
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
        out = subprocess.run([*args, tr("A Steam első indítása"), body],
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
    # Megvárjuk, amíg a felhasználó elindítja a Steamet (a mappát más is létrehozhatja előtte)
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
        # Ha a Steam közben kilépett (pl. a felhasználó leállította), legközelebb újra figyelünk
        gone = gone + 1 if not procs & STEAM_PROCS else 0
        if gone >= 3:
            break
        if time.monotonic() - started >= QUIET_S:
            mb = max(0, data_size() - start_size) // MB
            body = tr("A Steam letölti a saját frissítéseit. Ez pár percig is eltarthat, utána magától megnyílik.")
            if mb:
                body += "\n" + tr("{mb} MB letöltve", mb=mb)
            notification = notify(body, notification)
        time.sleep(POLL_S)
    if notification:
        close(notification)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
