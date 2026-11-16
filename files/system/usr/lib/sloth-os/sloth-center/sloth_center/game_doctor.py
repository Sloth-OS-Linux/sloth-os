"""What's wrong with the game? The texts and the notification (sloth_common/steam_doctor.py does the work).

Used by Sloth Center's Games page (games.py) and by the game-mode service (/usr/libexec/sloth-os/game-mode), which
sends the notification when a Steam game closed right after it started. The texts are here, in Sloth Center's
package, so the translation tools find them.
"""
import logging
import subprocess

from .i18n import N_, tr

log = logging.getLogger("sloth-center.game-doctor")

# The fixes (steam_doctor.STEPS), as the user reads them: "Sloth OS is trying: <this>". No "Proton" or "Wine".
STEP_TEXTS = {
    "nofsync": N_("a safer way for the game to wait for its own tasks"),
    "wined3d": N_("the older graphics mode (without Vulkan)"),
    "experimental": N_("the newest version of the Windows runtime"),
    "ge": N_("the community version of the Windows runtime, with fixes for many games"),
    "older": N_("an older version of the Windows runtime"),
}
NOTIFY_TITLE = N_("{game} closed right after it started")
NOTIFY_BODY = N_("Sloth OS can look for a setting that makes it start.")
NOTIFY_ACTION = N_("Look into it")


def step_text(key):
    return tr(STEP_TEXTS[key]) if key in STEP_TEXTS else ""


def notify(appid, name):
    """The notification with a button that opens the game's settings in Sloth Center (waits for the answer)."""
    from . import launch
    try:
        r = subprocess.run(["notify-send", "--app-name", tr("Sloth Center"), "--icon", "input-gamepad",
                            "--action=fix=" + tr(NOTIFY_ACTION), "--wait",
                            tr(NOTIFY_TITLE, game=name), tr(NOTIFY_BODY)],
                           capture_output=True, text=True, timeout=6 * 3600)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("notification: %s", e)
        return
    if r.stdout.strip() == "fix":
        launch.start(["sloth-center", "--page", "games", "--game", f"steam:{appid}"])
