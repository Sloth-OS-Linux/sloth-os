"""Recognizes programs built on WinUI 3 (the Windows App SDK; .NET MAUI's Windows apps use it too).

Wine cannot run WinUI 3 (it needs DirectComposition and the Windows App Runtime), so no Proton setting helps:
we say so in plain language instead of trying every setting. A real case: a .NET 10 MAUI app (2026-10-27).
"""
from pathlib import Path

from .i18n import tr

# The files a WinUI 3 program brings along (lowercase)
MARKERS = ("microsoft.winui.dll", "microsoft.windowsappruntime.bootstrap.dll")
# A single-file .NET program lists its files at the end of the .exe (the bundle manifest, uncompressed even when
# the files themselves are compressed); in a 99 MB program it was in the last 55 KB
TAIL_BYTES = 1024 * 1024


def detect(exe):
    """Whether the program is a WinUI 3 program: the marker files next to it, or named in its single-file bundle."""
    exe = Path(exe)
    try:
        if any(p.name.lower() in MARKERS for p in exe.parent.iterdir()):
            return True
    except OSError:
        pass
    try:
        with open(exe, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            tail = f.read().lower()
    except OSError:
        return False
    return any(m.encode() in tail for m in MARKERS)


def text(name):
    return tr("winui.unsupported", name=name)
