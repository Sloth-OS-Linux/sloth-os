"""Which runner a Windows program should start with.

Primary: umu-launcher + Proton (the best game compatibility). Proton and its
runtime (Steam Linux Runtime) are in the system from the factory; on first use they are
copied into the user's folder (SEED), and sloth-windows-prepare.timer downloads newer versions.
Fallback: the system's own Wine (wine-core RPM). It starts if Proton is not there yet
and there is no internet, so an .exe always starts, even without Steam and internet.
The user sees nothing of either (neither the word "Wine" nor "Proton").
"""
import os
import shutil
import subprocess
from pathlib import Path

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
# umu-launcher's locations (umu/umu_consts.py)
UMU_LOCAL = DATA_HOME / "umu"
PROTON_DIRS = [DATA_HOME / "Steam/compatibilitytools.d", DATA_HOME / "umu/compatibilitytools"]


# The bundled Proton and runtime (files/scripts/windows-runtime.sh); on first use this script copies them
# into the user's folder, without downloading
BUNDLED = Path("/usr/share/sloth-os/windows-runtime")
SEED = "/usr/libexec/sloth-os/windows-runtime-seed"


def bundled():
    """Whether the system has a bundled Proton and runtime."""
    return (BUNDLED / "steamrt3").is_dir() and any(BUNDLED.glob("UMU-Proton-*/proton"))


def local_runtime():
    """For a program started in the foreground: (Proton's folder, whether there is a runtime), without downloading.

    By default umu checks on every start whether there is a newer UMU-Proton and runtime, and if so, downloads them first
    (hundreds of MB). After a fresh install the bundled Proton is no longer the latest, so the first .exe was "loading"
    for minutes (2026-10-20, real machine). The user should not wait: we use what is already there (or the bundled one
    about to be copied in), and sloth-windows-prepare does the update in the background."""
    from . import heal
    proton = heal.newest(heal.UMU_LINE)
    path = heal.installed_protons().get(proton) if proton else None
    if not path and bundled():
        # the bundled copy: the runner copies it in first (SEED), to the same place
        name = sorted(p.name for p in BUNDLED.glob("UMU-Proton-*") if (p / "proton").is_file())[-1]
        path = PROTON_DIRS[0] / name
    runtime = UMU_LOCAL.is_dir() and any((d / "VERSIONS.txt").is_file() for d in UMU_LOCAL.iterdir() if d.is_dir())
    return (str(path) if path else None), runtime or bundled()


def proton_ready():
    """Whether the runtime and Proton are already downloaded (then it starts without internet too)."""
    runtime = UMU_LOCAL.is_dir() and any((d / "VERSIONS.txt").is_file() for d in UMU_LOCAL.iterdir() if d.is_dir())
    proton = any(p.name.startswith(("UMU-Proton", "GE-Proton")) and (p / "proton").is_file()
                 for base in PROTON_DIRS if base.is_dir() for p in base.iterdir())
    return runtime and proton


def online():
    """Whether there is internet according to NetworkManager (without an external request). If we do not know, we assume yes."""
    try:
        out = subprocess.run(["nmcli", "--terse", "--fields", "CONNECTIVITY", "general"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return True
    return out in ("full", "unknown", "")


def use_wine():
    """True if it has to start with the system's Wine (no Proton, no network, but Wine is there)."""
    return not proton_ready() and not bundled() and not online() and shutil.which("wine") is not None
