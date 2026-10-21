"""Recognizes anti-cheat in the game's folder, so we can say clearly what is going on.

Some anti-cheats never run on Linux (the vendor forbids it or it is kernel-level),
others (Easy Anti-Cheat, BattlEye) depend on the game developer's decision.
"""
from pathlib import Path

from .i18n import tr

# (name, file/folder patterns in lowercase, whether it runs on Linux at all)
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
    """Returns: (name, runs_on_linux) or None.

    We look at the game's folder and its subfolders, and only at the direct files of the parent folder
    (e.g. Valorant: ../vgc.exe next to live/VALORANT.exe). We do not look into the parent's subfolders,
    because other games may be there.
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
    return tr("anticheat.blocked", game=game, system=system)


def maybe_text(game, system):
    return tr("anticheat.maybe", game=game, system=system)
