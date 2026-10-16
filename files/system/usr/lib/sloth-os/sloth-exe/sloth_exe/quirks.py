"""Ismert programok beállításai, hogy Steam nélkül, közvetlenül is rendesen fussanak.

Egy-egy indítóprogram (pl. a Battle.net) csak néhány apró beállítással fut jól; ezeket
indítás előtt magunk állítjuk be, a felhasználónak nem kell tudnia róluk. A receptek a
Lutris bevált telepítőiből jönnek (https://lutris.net/games/<indító>/), a Protonhoz igazítva:
amit a Proton magától megold (pl. a betűtípusok), azt kihagyjuk.

Egy recept: (felismerés, beállítás). A beállítás módosíthatja a környezetet és a program
beállításfájljait, és visszaadhat:
  "args":  paraméterek a programnak (csak magára az indítóra, a belőle indított játékokra nem),
  "verbs": hiányzó Windows-összetevők (winetricks, az első indítás előtt egyszer települnek).

Rövid életű indítók (launch_target): az umu és a Proton csak az elindított folyamatot várja meg
(a waitforexitandrun a korábbi munkamenet végét várja meg indítás előtt, nem a gyerekfolyamatokat).
Ha egy indító átadja a helyét a kliensnek és kilép, a futtató leáll, és a kliens ablaka is vele
együtt eltűnik; ezért ilyenkor magát a klienst indítjuk.
"""
import getpass
import json
import logging

from .programs import WIN_USER

log = logging.getLogger("sloth-exe.quirks")


def _windows_users(prefix):
    """A Windows-felhasználók mappái (a Protonnál "steamuser", a tartalék Wine-nál a Linuxos név)."""
    users = prefix / "drive_c/users"
    found = [d for d in users.iterdir() if d.is_dir() and d.name != "Public"] if users.is_dir() else []
    return found or [users / WIN_USER, users / getpass.getuser()]


def _override(env, value):
    overrides = env.value("WINEDLLOVERRIDES")
    env.insert("WINEDLLOVERRIDES", f"{overrides};{value}" if overrides else value)


def _matches(program, exe, dirs, names):
    """A program mappájában ott van-e az indító, vagy ez maga (vagy a telepítője)."""
    name = exe.name.lower()
    return any((program.prefix / d).is_dir() for d in dirs) or any(n in name for n in names)


# --- Battle.net --------------------------------------------------------------------------------------

def _battlenet(program, exe, env):
    if not _matches(program, exe, ["drive_c/Program Files (x86)/Battle.net"], ["battle.net"]):
        return None
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
    # A helymeghatározás Wine alatt az indításnál elakaszthatja a klienst
    _override(env, "locationapi=d")
    return {}


# Indító -> kliens (ugyanabban a mappában). A „Battle.net Launcher.exe” (erre mutat a parancsikon)
# csak elindítja a klienst, és pár mp múlva kilép: vele együtt leállt a futtató, és a már megjelent
# ablak is bezárult (Steamből azért ment, mert a Steam minden folyamatot megvár). A Lutris
# Blizzard-receptjei is a Battle.net.exe-t indítják.
LAUNCHER_STUBS = {"battle.net launcher.exe": "Battle.net.exe"}


def launch_target(exe):
    """A ténylegesen indítandó .exe: rövid életű indító helyett maga a kliens, ha megvan."""
    client = LAUNCHER_STUBS.get(exe.name.lower())
    if client and (exe.parent / client).is_file():
        log.info("%s helyett a kliens indul: %s", exe.name, client)
        return exe.parent / client
    return exe


# --- Ubisoft Connect ---------------------------------------------------------------------------------

UBISOFT_SETTINGS = ("overlay:\n  enabled: false\n  forceunhookgame: false\n  fps_enabled: false\n"
                    "  warning_enabled: false\nuser:\n  closebehavior: CloseBehavior_Close\n")


def _ubisoft(program, exe, env):
    if not _matches(program, exe, ["drive_c/Program Files (x86)/Ubisoft/Ubisoft Game Launcher"],
                    ["ubisoftconnect", "upc.exe", "uplay"]):
        return None
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
    return {"verbs": ["d3dcompiler_43"]}


# --- Epic Games ------------------------------------------------------------------------------------------

def _epic(program, exe, env):
    if not _matches(program, exe, ["drive_c/Program Files/Epic Games/Launcher",
                                   "drive_c/Program Files (x86)/Epic Games/Launcher"], ["epicgameslauncher"]):
        return None
    # A beépített böngészőmotor Vulkan/D3D alatt gyakran fekete ablakot ad; OpenGL-lel megy
    if exe.name.lower() == "epicgameslauncher.exe":
        return {"args": ["-opengl", "-SkipBuildPatchPrereq"]}
    return {}


# --- GOG Galaxy ------------------------------------------------------------------------------------------

def _gog(program, exe, env):
    if not _matches(program, exe, ["drive_c/Program Files/GOG Galaxy", "drive_c/Program Files (x86)/GOG Galaxy"],
                    ["galaxyclient", "gog_galaxy", "goggalaxy"]):
        return None
    out = {"verbs": ["vcrun2022", "dotnet48"]}
    if exe.name.lower() == "galaxyclient.exe":
        # A beépített böngészőmotor OpenGL ES-e Wine alatt hibás; a frissítő és a rendszergazdai mód nem kell
        _override(env, "libglesv2=d")
        out["args"] = ["/runWithoutUpdating", "/deelevated"]
    return out


QUIRKS = [_battlenet, _ubisoft, _epic, _gog]
# EA app, Rockstar Games Launcher: a Lutris csak betűtípusokat tesz fel, azokat a Proton már hozza


def apply(program, exe, env):
    """Indítás előtt: a program ismert beállításai (env: QProcessEnvironment, helyben módosul).

    -> {"args": [...], "verbs": [...]} a futtatónak.
    """
    out = {"args": [], "verbs": []}
    for quirk in QUIRKS:
        try:
            extra = quirk(program, exe, env)
        except Exception as e:  # egy recept hibája ne akadályozza az indítást
            log.warning("%s: %s", quirk.__name__, e)
            continue
        if extra is not None:
            out["args"] += extra.get("args", [])
            out["verbs"] += [v for v in extra.get("verbs", []) if v not in out["verbs"]]
    return out
