"""Settings of known programs, so they run properly directly too, without Steam.

Some launchers (e.g. Battle.net) only run well with a few small settings; we set these ourselves
before starting, and the user does not need to know about them. It has two parts:
  - the recipes (sloth_common.apps.recipes): as data, updated with the system and from the shared knowledge:
    components, Proton switches, program arguments, DLL overrides, and which client should start instead of a
    short-lived launcher. They come from Lutris' proven installers, adapted to Proton;
  - here, as code, only what writes the programs' own settings files (Battle.net, Ubisoft Connect).

Short-lived launchers (launch_target): umu and Proton only wait for the started process
(waitforexitandrun waits for the previous session's end before starting, not for the child processes).
If a launcher hands over to the client and exits, the runner stops, and the client's window disappears
together with it; so in that case we start the client itself (e.g. instead of "Battle.net Launcher.exe" the
„Battle.net.exe”-t, ahogy a Lutris Blizzard-receptjei is).
"""
import getpass
import json
import logging

from sloth_common.apps import recipes
from sloth_common.apps.library import WIN_USER

log = logging.getLogger("sloth-exe.quirks")


def _windows_users(prefix):
    """The Windows users' folders (with Proton "steamuser", with the fallback Wine the Linux name)."""
    users = prefix / "drive_c/users"
    found = [d for d in users.iterdir() if d.is_dir() and d.name != "Public"] if users.is_dir() else []
    return found or [users / WIN_USER, users / getpass.getuser()]


def _override(env, value):
    overrides = env.value("WINEDLLOVERRIDES")
    env.insert("WINEDLLOVERRIDES", f"{overrides};{value}" if overrides else value)


def _matches(program, exe, recipe_id):
    return any(r["id"] == recipe_id for r in recipes.matching(program.prefix, exe))


# --- Settings files ------------------------------------------------------------------------------

def _battlenet(program, exe):
    if not _matches(program, exe, "battlenet"):
        return
    # The built-in browser engine's GPU acceleration crashes under Wine after loading:
    # the window disappears, and the program exits a few seconds later
    for user in _windows_users(program.prefix):
        path = user / "AppData/Roaming/Battle.net/Battle.net.config"
        try:
            config = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError):
            config = {}
        client = config.setdefault("Client", {})
        if client.get("HardwareAcceleration") == "false":
            continue
        client["HardwareAcceleration"] = "false"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config, indent=4), encoding="utf-8")
            log.info("Battle.net: hardware acceleration turned off (%s)", path)
        except OSError as e:
            log.warning("Battle.net setting: %s", e)


UBISOFT_SETTINGS = ("overlay:\n  enabled: false\n  forceunhookgame: false\n  fps_enabled: false\n"
                    "  warning_enabled: false\nuser:\n  closebehavior: CloseBehavior_Close\n")


def _ubisoft(program, exe):
    if not _matches(program, exe, "ubisoft-connect"):
        return
    # The in-game overlay causes crashes under Wine: turned off (if the user has no setting of their own yet)
    for user in _windows_users(program.prefix):
        path = user / "AppData/Local/Ubisoft Game Launcher/settings.yaml"
        if not path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(UBISOFT_SETTINGS, encoding="utf-8")
                log.info("Ubisoft Connect: overlay turned off (%s)", path)
            except OSError as e:
                log.warning("Ubisoft Connect setting: %s", e)


CONFIG_WRITERS = [_battlenet, _ubisoft]
# EA app, Rockstar Games Launcher: Lutris only installs fonts, and Proton brings those already


def launch_target(exe):
    """The .exe to actually start: the client itself instead of a short-lived launcher, if a recipe knows it and it exists."""
    target = recipes.stub_target(exe)
    if target and target != exe and target.is_file():
        log.info("the client starts instead of %s: %s", exe.name, target)
        return target
    return exe


def apply(program, exe, env):
    """Before starting: the program's known settings (env: QProcessEnvironment, modified in place).

    -> {"args": [...], "verbs": [...]} for the runner.
    """
    for writer in CONFIG_WRITERS:
        try:
            writer(program, exe)
        except Exception as e:  # an error in one setting must not prevent the start
            log.warning("%s: %s", writer.__name__, e)
    known = recipes.settings(program.prefix, exe)
    for value in known["dll_overrides"]:
        _override(env, value)
    for name in known["env"]:
        env.insert(name, "1")
    if any(known.values()):
        log.info("receptek: %s", {k: v for k, v in known.items() if v})
    return {"args": known["args"], "verbs": known["verbs"]}
