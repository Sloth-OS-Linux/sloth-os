"""Ismert programok beállításai, hogy Steam nélkül, közvetlenül is rendesen fussanak.

Egy-egy indítóprogram (pl. a Battle.net) csak néhány apró beállítással fut jól; ezeket indítás előtt
magunk állítjuk be, a felhasználónak nem kell tudnia róluk. Két része van:
  - a receptek (sloth_common.apps.recipes): adatként, a rendszerrel és a közös tudásból frissítve:
    összetevők, Proton-kapcsolók, programparaméterek, DLL-kikapcsolások, és hogy melyik rövid életű
    indító helyett a kliens induljon. A Lutris bevált telepítőiből jönnek, a Protonhoz igazítva;
  - itt, kódként, csak az, ami a programok saját beállításfájljait írja (Battle.net, Ubisoft Connect).

Rövid életű indítók (launch_target): az umu és a Proton csak az elindított folyamatot várja meg
(a waitforexitandrun a korábbi munkamenet végét várja meg indítás előtt, nem a gyerekfolyamatokat).
Ha egy indító átadja a helyét a kliensnek és kilép, a futtató leáll, és a kliens ablaka is vele
együtt eltűnik; ezért ilyenkor magát a klienst indítjuk (pl. „Battle.net Launcher.exe” helyett a
„Battle.net.exe”-t, ahogy a Lutris Blizzard-receptjei is).
"""
import getpass
import json
import logging

from sloth_common.apps import recipes
from sloth_common.apps.library import WIN_USER

log = logging.getLogger("sloth-exe.quirks")


def _windows_users(prefix):
    """A Windows-felhasználók mappái (a Protonnál "steamuser", a tartalék Wine-nál a Linuxos név)."""
    users = prefix / "drive_c/users"
    found = [d for d in users.iterdir() if d.is_dir() and d.name != "Public"] if users.is_dir() else []
    return found or [users / WIN_USER, users / getpass.getuser()]


def _override(env, value):
    overrides = env.value("WINEDLLOVERRIDES")
    env.insert("WINEDLLOVERRIDES", f"{overrides};{value}" if overrides else value)


def _matches(program, exe, recipe_id):
    return any(r["id"] == recipe_id for r in recipes.matching(program.prefix, exe))


# --- Beállításfájlok ------------------------------------------------------------------------------

def _battlenet(program, exe):
    if not _matches(program, exe, "battlenet"):
        return
    # A beépített böngészőmotor GPU-gyorsítása Wine alatt betöltés után összeomlik:
    # az ablak eltűnik, a program pár másodperc múlva kilép
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
            log.info("Battle.net: hardveres gyorsítás kikapcsolva (%s)", path)
        except OSError as e:
            log.warning("Battle.net beállítás: %s", e)


UBISOFT_SETTINGS = ("overlay:\n  enabled: false\n  forceunhookgame: false\n  fps_enabled: false\n"
                    "  warning_enabled: false\nuser:\n  closebehavior: CloseBehavior_Close\n")


def _ubisoft(program, exe):
    if not _matches(program, exe, "ubisoft-connect"):
        return
    # A játékon belüli overlay Wine alatt összeomlást okoz: kikapcsolva (ha a felhasználónak még nincs beállítása)
    for user in _windows_users(program.prefix):
        path = user / "AppData/Local/Ubisoft Game Launcher/settings.yaml"
        if not path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(UBISOFT_SETTINGS, encoding="utf-8")
                log.info("Ubisoft Connect: overlay kikapcsolva (%s)", path)
            except OSError as e:
                log.warning("Ubisoft Connect beállítás: %s", e)


CONFIG_WRITERS = [_battlenet, _ubisoft]
# EA app, Rockstar Games Launcher: a Lutris csak betűtípusokat tesz fel, azokat a Proton már hozza


def launch_target(exe):
    """A ténylegesen indítandó .exe: rövid életű indító helyett maga a kliens, ha egy recept ismeri, és megvan."""
    target = recipes.stub_target(exe)
    if target and target != exe and target.is_file():
        log.info("%s helyett a kliens indul: %s", exe.name, target)
        return target
    return exe


def apply(program, exe, env):
    """Indítás előtt: a program ismert beállításai (env: QProcessEnvironment, helyben módosul).

    -> {"args": [...], "verbs": [...]} a futtatónak.
    """
    for writer in CONFIG_WRITERS:
        try:
            writer(program, exe)
        except Exception as e:  # egy beállítás hibája ne akadályozza az indítást
            log.warning("%s: %s", writer.__name__, e)
    known = recipes.settings(program.prefix, exe)
    for value in known["dll_overrides"]:
        _override(env, value)
    for name in known["env"]:
        env.insert(name, "1")
    if any(known.values()):
        log.info("receptek: %s", {k: v for k, v in known.items() if v})
    return {"args": known["args"], "verbs": known["verbs"]}
