"""Ismert programok beállításai, hogy Steam nélkül, közvetlenül is rendesen fussanak.

Egy-egy indítóprogram (pl. a Battle.net) csak néhány apró beállítással fut jól; ezeket
indítás előtt magunk állítjuk be, a felhasználónak nem kell tudnia róluk. A receptek a
Lutris bevált telepítőiből jönnek (https://lutris.net/games/battlenet/).
"""
import getpass
import json
import logging

from .programs import WIN_USER

log = logging.getLogger("sloth-exe.quirks")

BATTLENET_DIR = "drive_c/Program Files (x86)/Battle.net"


def _windows_users(prefix):
    """A Windows-felhasználók mappái (a Protonnál "steamuser", a tartalék Wine-nál a Linuxos név)."""
    users = prefix / "drive_c/users"
    found = [d for d in users.iterdir() if d.is_dir() and d.name != "Public"] if users.is_dir() else []
    return found or [users / WIN_USER, users / getpass.getuser()]


def _battlenet(program, exe, env):
    if not ((program.prefix / BATTLENET_DIR).is_dir() or "battle.net" in exe.name.lower()):
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
    # A helymeghatározás Wine alatt az indításnál elakaszthatja a klienst
    overrides = env.value("WINEDLLOVERRIDES")
    env.insert("WINEDLLOVERRIDES", f"{overrides};locationapi=d" if overrides else "locationapi=d")


QUIRKS = [_battlenet]


def apply(program, exe, env):
    """Indítás előtt: a program ismert beállításai (env: QProcessEnvironment, helyben módosul)."""
    for quirk in QUIRKS:
        try:
            quirk(program, exe, env)
        except Exception as e:  # egy recept hibája ne akadályozza az indítást
            log.warning("%s: %s", quirk.__name__, e)
