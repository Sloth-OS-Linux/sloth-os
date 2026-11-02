"""The question at a new network, as in Windows: is it a home network (shared folders open, the computer shows up),
a private one (a workplace: they open, the computer does not show up by itself) or a public one (hidden)?

It runs in the user's session (sloth-network-notify.path / .service) whenever the network state changes
(/run/sloth-os/sharing/state.json, written by /usr/libexec/sloth-os/file-sharing) and at login. A network not asked
about yet counts as public; closing the notification leaves it public, and it is not asked again (Sloth Center →
Disks can change it). The networks saved before this existed became home networks once, so sharing kept working:
that is told once too. Setting the kind needs no password (sloth-helper-network).
Start: python3 -m sloth_center.network_notify
"""
import json
import os
import subprocess
from pathlib import Path

from .i18n import tr

STATE = Path("/run/sloth-os/sharing/state.json")
HELPER = "/usr/libexec/sloth-os/sloth-helper-network"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os"
ASKED = STATE_DIR / "networks-asked.json"
DEFAULTED_TOLD = STATE_DIR / "networks-defaulted-told"


def notify(title, body, actions, icon="network-wireless"):
    """A notification that waits for the answer: the chosen action's id, or "" if it was closed."""
    cmd = ["notify-send", "--app-name=Sloth OS", f"--icon={icon}", "--expire-time=0"]
    cmd += [f"--action={key}={label}" for key, label in actions]
    try:
        r = subprocess.run(cmd + [title, body], capture_output=True, text=True)
    except OSError:
        return ""
    return r.stdout.strip()


def tell_defaulted(names):
    """Once: the saved networks count as home networks."""
    if not names or DEFAULTED_TOLD.exists():
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULTED_TOLD.write_text("1\n")
    answer = notify(tr("Your saved networks count as home networks"),
                    tr("Shared folders work on them as before: {names}. If one of them is public (a café, a hotel), "
                       "change it in Sloth Center → Disks.", names=", ".join(names)),
                    [("open", tr("Open Sloth Center"))], icon="network-workgroup")
    if answer == "open":
        subprocess.Popen(["sloth-center", "--page", "disks"])


def main():
    try:
        state = json.loads(STATE.read_text())
    except (OSError, ValueError):
        return 0
    tell_defaulted([n for n in state.get("defaulted", []) if isinstance(n, str)])
    try:
        asked = set(json.loads(ASKED.read_text()))
    except (OSError, ValueError, TypeError):
        asked = set()
    for network in state.get("networks", []):
        uuid = network.get("uuid")
        if not network.get("connected") or network.get("kind") or not uuid or uuid in asked:
            continue
        # asked once only, also when another session answers first
        asked.add(uuid)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        ASKED.write_text(json.dumps(sorted(asked)))
        answer = notify(tr("New network: {name}", name=network.get("name", "")),
                        tr("What kind of network is it? At home, other computers see this computer and can open the "
                           "folders you share. On a private network (a workplace), they can open them, but this "
                           "computer doesn't show up by itself. On a public network (a café, a hotel), this computer "
                           "stays hidden."),
                        [("home", tr("Home")), ("private", tr("Private")), ("public", tr("Public"))])
        # closed without an answer: public, the safe one (it can be changed in Sloth Center → Disks)
        kind = answer if answer in ("home", "private") else "public"
        subprocess.run(["pkexec", HELPER, "network-kind", uuid, kind], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
