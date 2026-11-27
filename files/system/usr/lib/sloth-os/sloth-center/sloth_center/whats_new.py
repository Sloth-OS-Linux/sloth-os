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
    "2.1": [
        N_("Restore points: before bigger changes Sloth OS keeps the system as it was, and the Updates page can take it back."),
        N_("Every update in one place: the Windows programs' updates are on the Updates page too."),
        N_("The PIN is kept in the computer's security chip (TPM), and it can also open your saved passwords at sign-in, like Windows Hello."),
        N_("Driver options in Advanced settings: the known fixes for this computer, and your own options."),
        N_("Game fixes from other players for Steam games too, with how many players they helped and when."),
    ],
    "2.0": [
        N_("TV mode: Steam's big-screen interface on the whole screen, like a game console, with your games from other stores too. It is in the Start menu."),
        N_("Older computers: Sloth OS now also installs on PCs that start in the old BIOS mode."),
        N_("A lighter desktop for weak computers: it turns itself on where it helps, and Appearance has a switch for it."),
        N_("A file that no app opens yet offers the right app, installs it with one click and opens the file."),
        N_("Moving over from another Linux: your files, bookmarks, apps and Steam games come over, as from Windows."),
        N_("Feedback hides your personal details and shows exactly what is sent."),
    ],
    "1.6": [
        N_("One settings app: every setting of the computer is in Sloth Center now, the everyday ones first, the rest "
           "under More settings."),
        N_("A search at the top of Sloth Center finds any setting."),
        N_("Wi-Fi has a page of its own: connect, forget a network, turn Wi-Fi on and off."),
        N_("Apps: every installed app in one list, with Open and Remove."),
        N_("Parental controls: \u201cAsk for more time\u201d now asks a parent, and the website filter covers every "
           "program."),
    ],
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
