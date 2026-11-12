"""Opening Sloth Center (or another program) from a notification's button.

The notifications run as systemd user services (Type=oneshot). When such a service's process ends, systemd stops
the unit and kills everything still in its cgroup, so a program started with subprocess.Popen from there is killed
at once (the "See what's new" button opened nothing, 2026-11-12, HP). systemd-run starts it as its own transient
unit instead, outside the service; the session's display and language variables are passed on.
"""
import os
import subprocess

PASS_ENV = ("WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
            "DBUS_SESSION_BUS_ADDRESS", "LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "QT_QPA_PLATFORMTHEME",
            "KDE_FULL_SESSION")


def start(args):
    """Starts `args` so that it outlives the calling service. -> True if it was started."""
    envs = [f"--setenv={k}={os.environ[k]}" for k in PASS_ENV if os.environ.get(k)]
    try:
        r = subprocess.run(["systemd-run", "--user", "--collect", "--quiet"] + envs + ["--"] + list(args),
                           capture_output=True, timeout=20)
        if r.returncode == 0:
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    try:   # not under systemd (e.g. started by hand): an ordinary child is fine there
        subprocess.Popen(list(args), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def open_center(page):
    return start(["sloth-center", "--page", page])
