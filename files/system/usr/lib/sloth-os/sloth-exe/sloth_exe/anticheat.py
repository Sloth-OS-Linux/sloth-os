"""Csalásvédelem felismerése a játék mappájában, hogy érthetően szólhassunk.

Néhány csalásvédelem Linuxon soha nem fut (a gyártó tiltja vagy kernel-szintű),
mások (Easy Anti-Cheat, BattlEye) a játék fejlesztőjének döntésén múlnak.
"""
from pathlib import Path

# (név, fájl/mappa minták kisbetűvel, Linuxon fut-e egyáltalán)
SYSTEMS = [
    ("Riot Vanguard", ("vgc.exe", "vgk.sys", "vanguard"), False),
    ("FACEIT", ("faceit.exe", "faceitservice.exe", "faceit"), False),
    ("Ricochet", ("ricochet",), False),
    ("nProtect GameGuard", ("gameguard.des", "gamemon.des", "gameguard"), False),
    ("XIGNCODE", ("xigncode", "x3.xem"), False),
    ("Easy Anti-Cheat", ("easyanticheat", "easyanticheat_eos", "start_protected_game.exe"), True),
    ("BattlEye", ("battleye", "beservice.exe", "beclient.dll", "beclient_x64.dll"), True),
]


def detect(exe):
    """Visszaadja: (név, fut_linuxon) vagy None.

    A játék mappáját és annak almappáit nézzük, a szülőmappából csak a közvetlen
    fájlokat (pl. Valorant: live/VALORANT.exe mellett ../vgc.exe). A szülő almappáiba
    nem nézünk bele, mert ott más játékok is lehetnek.
    """
    exe = Path(exe)
    names = set()
    try:
        for p in exe.parent.iterdir():
            names.add(p.name.lower())
            if p.is_dir():
                try:
                    names.update(c.name.lower() for c in p.iterdir())
                except OSError:
                    pass
    except OSError:
        pass
    try:
        names.update(p.name.lower() for p in exe.parent.parent.iterdir() if p.is_file())
    except OSError:
        pass
    for name, patterns, works in SYSTEMS:
        if any(any(n == pat or n.startswith(pat) for n in names) for pat in patterns):
            return name, works
    return None


def blocked_text(game, system):
    return (f"A(z) {game} a(z) {system} csalásvédelmet használja, ami Linuxon nem engedi futni a játékot. "
            "Ez nem a gépeden múlik, és mi sem tudjuk megkerülni. Sajnos ezt a játékot itt nem lehet játszani.")


def maybe_text(game, system):
    return (f"A(z) {game} a(z) {system} csalásvédelmet használja. Ez Linuxon csak akkor működik, ha a játék "
            "készítői engedélyezték. Ha a játék nem indul vagy kidob, valószínűleg ez az oka. Érdemes megnézni, "
            "van-e a játéknak Steames változata.")
