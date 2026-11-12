"""What's new: after an update brought a new Sloth OS version, a few plain sentences about what it brought.

At sign-in (sloth-whats-new.service) a notification says that Sloth OS was updated, with a button that opens Sloth
Center's Updates page, where the "What's new in Sloth OS …" card lists the same. It speaks up once per version, and
not at all on a freshly installed system (there everything is new; the first sign-in only remembers the version).
The notes are Sloth Center texts (NOTES below), translated like the rest of it.
Start: python3 -m sloth_center.whats_new
"""
import os
import subprocess
from pathlib import Path

from sloth_common import quiet_hours

from . import launch
from .i18n import N_, tr

SEEN = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "whats-new-seen"
OS_RELEASE = Path("/usr/lib/os-release")
WELCOME_DONE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os" / "welcome-done"

# Sloth OS version -> what it brought, for everyone (not developers): a few short sentences, the biggest first
NOTES = {
    "1.5": [
        N_("Moving over from Windows: your files, bookmarks (straight into your browsers), Steam games with their "
           "saves, and a list of the programs you used, with their Sloth OS versions."),
        N_("BIOS and device firmware updates in Sloth Center → Updates, only when you choose to."),
        N_("Help from someone you know: in Sloth Center → Help, they can see your screen and help over the internet."),
        N_("Printers and scanners: a page in Sloth Center with a test page and scanning."),
        N_("Parental controls: child accounts with screen time, allowed apps and safe websites."),
        N_("A guest account that forgets everything when the guest signs out."),
        N_("Accessibility, and Power and battery pages in Sloth Center."),
        N_("Game saves can be backed up by themselves."),
        N_("Create New → Website shortcut… on the desktop and in the file manager."),
    ],
}


def current_version():
    """"1.5" from os-release's VERSION ("1.5 (Fedora Atomic 44)"), or ""."""
    try:
        for line in OS_RELEASE.read_text().splitlines():
            if line.startswith("VERSION="):
                return line.split("=", 1)[1].strip().strip('"').split(" ")[0]
    except OSError:
        pass
    return ""


def notes(version=None):
    """The translated notes of a version (by default the running one), or []."""
    return [tr(n) for n in NOTES.get(version if version is not None else current_version(), [])]


def main():
    version = current_version()
    if not version:
        return 0
    try:
        seen = SEEN.read_text().strip()
    except OSError:
        # never remembered: an account that went through Welcome before this existed (an update: tell it), or a
        # new one whose Welcome is still ahead (a fresh install: nothing to tell)
        seen = "" if WELCOME_DONE.exists() else None
    if seen == version:
        return 0
    if seen is not None and NOTES.get(version) and quiet_hours.defer("sloth_center.whats_new"):
        return 0          # quiet hours: at the next sign-in or when they end
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(version + "\n")
    if seen is None or not NOTES.get(version):
        return 0          # a fresh install (or a version without notes): nothing to tell
    try:
        answer = subprocess.run(
            ["notify-send", "--app-name=Sloth OS", "--icon=sloth-os", "--expire-time=0",
             "--action=show=" + tr("See what's new"), tr("Sloth OS {version} is here", version=version),
             "\n".join("• " + n for n in notes(version)[:3])],
            capture_output=True, text=True).stdout.strip()
    except OSError:
        return 0
    if answer == "show":
        launch.open_center("updates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
