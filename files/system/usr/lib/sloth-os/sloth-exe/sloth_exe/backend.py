"""Melyik futtatóval induljon egy Windows-program.

Elsődleges: umu-launcher + Proton (a legjobb játékkompatibilitás). A Proton és a hozzá
tartozó futtatókörnyezet (Steam Linux Runtime) gyárilag a rendszerben van; első használatkor a
felhasználó mappájába másolódik (SEED), az újabb verziókat a sloth-windows-prepare.timer tölti le.
Tartalék: a rendszer saját Wine-ja (wine-core RPM). Akkor indul, ha a Proton még nincs
meg és nincs internet, így egy .exe mindig elindul, Steam és internet nélkül is.
A felhasználó egyikből sem lát semmit (sem a "Wine", sem a "Proton" szót).
"""
import os
import shutil
import subprocess
from pathlib import Path

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
# az umu-launcher helyei (umu/umu_consts.py)
UMU_LOCAL = DATA_HOME / "umu"
PROTON_DIRS = [DATA_HOME / "Steam/compatibilitytools.d", DATA_HOME / "umu/compatibilitytools"]


# A gyári Proton és futtatókörnyezet (files/scripts/windows-runtime.sh); első használatkor ez a script másolja
# a felhasználó mappájába, letöltés nélkül
BUNDLED = Path("/usr/share/sloth-os/windows-runtime")
SEED = "/usr/libexec/sloth-os/windows-runtime-seed"


def bundled():
    """Van-e gyári Proton és futtatókörnyezet a rendszerben."""
    return (BUNDLED / "steamrt3").is_dir() and any(BUNDLED.glob("UMU-Proton-*/proton"))


def proton_ready():
    """Le van-e már töltve a futtatókörnyezet és a Proton (akkor internet nélkül is indul)."""
    runtime = UMU_LOCAL.is_dir() and any((d / "VERSIONS.txt").is_file() for d in UMU_LOCAL.iterdir() if d.is_dir())
    proton = any(p.name.startswith(("UMU-Proton", "GE-Proton")) and (p / "proton").is_file()
                 for base in PROTON_DIRS if base.is_dir() for p in base.iterdir())
    return runtime and proton


def online():
    """A NetworkManager szerint van-e internet (külső kérés nélkül). Ha nem tudjuk, igennek vesszük."""
    try:
        out = subprocess.run(["nmcli", "--terse", "--fields", "CONNECTIVITY", "general"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return True
    return out in ("full", "unknown", "")


def use_wine():
    """Igaz, ha a rendszer Wine-jával kell indítani (nincs Proton, nincs net, de van Wine)."""
    return not proton_ready() and not bundled() and not online() and shutil.which("wine") is not None
