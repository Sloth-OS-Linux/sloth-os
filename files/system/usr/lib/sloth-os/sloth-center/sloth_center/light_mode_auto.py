"""At sign-in: on a weak computer the lighter mode turns on by itself, once (sloth_common.light_mode).

Runs in the user's session (sloth-light-mode.service). Only when this user has never had it decided: after that,
whatever they choose in Sloth Center (Appearance) stays. A notification says what happened, with a button to the
setting. Start: python3 -m sloth_center.light_mode_auto
"""
import subprocess

from sloth_common import light_mode

from . import launch
from .i18n import N_, tr

REASON_TEXTS = {
    "memory": N_("it has little memory"),
    "processor": N_("its processor is slow"),
    "graphics": N_("its graphics card has no driver that can draw"),
}


def main():
    if light_mode.load_state().get("decided"):
        return 0
    why = light_mode.reasons()
    if not why:
        return 0        # nothing to do; checked again at the next sign-in
    light_mode.set_on(True, auto=True)
    body = tr("This computer is a little weak ({reasons}), so Sloth OS turned off the animations and the blur "
              "effect, and file search looks at names only. Everything works the same, just lighter. You can "
              "change it in Sloth Center → Appearance.").format(reasons=", ".join(tr(REASON_TEXTS[r]) for r in why))
    if notify(tr("Lighter desktop"), body, tr("Settings")) == "open":
        launch.open_center("appearance")
    return 0


def notify(title, body, button):
    """The notification; -> "open" if its button was clicked."""
    try:
        r = subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=speedometer", "--expire-time=0",
                            "--action=open=" + button, title, body],
                           capture_output=True, text=True, timeout=24 * 3600)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip()

if __name__ == "__main__":
    raise SystemExit(main())
