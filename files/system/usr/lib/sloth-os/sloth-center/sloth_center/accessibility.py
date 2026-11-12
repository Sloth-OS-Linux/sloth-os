"""Accessibility: what Windows has under Settings → Accessibility, in one place (Sloth Center → Accessibility).

Everything here is the user's own setting, in KDE's own files, so KDE's settings show the same (no password):
  - text size: the sizes of the desktop's fonts in kdeglobals (100–200%, from the 10-point default);
  - a bigger pointer: the cursor size (plasma-apply-cursortheme --size, at once);
  - high contrast: the SlothHighContrast color scheme; the scheme before it comes back when it is turned off;
  - less motion: KDE's animations off (AnimationDurationFactor=0);
  - the screen reader (Orca): kaccessrc [ScreenReader], kaccess starts and stops it;
  - the magnifier: KWin's zoom effect (Meta and + / − zooms in and out);
  - sticky keys: Ctrl, Shift, Alt one after another instead of together (kaccessrc [Keyboard]).
The state that KDE does not keep (the chosen text size, the scheme before high contrast) is in
~/.config/sloth-os/accessibility.json.
"""
import json
import logging
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

log = logging.getLogger("sloth-center.accessibility")

STATE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sloth-os/accessibility.json"
TEXT_SCALES = (100, 125, 150, 200)
CURSOR_SIZES = (24, 36, 48)
CONTRAST_SCHEME = "SlothHighContrast"
DEFAULT_SCHEME = "SlothSilverDark"
# (file group, key, size at 100%, the font when the key is not set)
FONTS = (("General", "font", 10, "Noto Sans,10,-1,5,50,0,0,0,0,0"),
         ("General", "menuFont", 10, "Noto Sans,10,-1,5,50,0,0,0,0,0"),
         ("General", "toolBarFont", 10, "Noto Sans,10,-1,5,50,0,0,0,0,0"),
         ("General", "smallestReadableFont", 8, "Noto Sans,8,-1,5,50,0,0,0,0,0"),
         ("General", "fixed", 10, "Noto Sans Mono,10,-1,5,50,0,0,0,0,0"),
         ("WM", "activeFont", 10, "Noto Sans,10,-1,5,50,0,0,0,0,0"))
FONT_CHANGED, CURSOR_CHANGED = 1, 5  # KGlobalSettings change types


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return None


def read(file, group, key, default=""):
    groups = sum((["--group", g] for g in group.split("][")), [])
    r = _run(["kreadconfig6", "--file", file, *groups, "--key", key, "--default", default])
    return r.stdout.strip() if r and r.returncode == 0 else default


def write(file, group, key, value=None, kind=None):
    """A KDE setting written with --notify (running KDE programs see it); None deletes the key."""
    groups = sum((["--group", g] for g in group.split("][")), [])
    cmd = ["kwriteconfig6", "--notify", "--file", file, *groups, "--key", key]
    if value is None:
        cmd.append("--delete")
    else:
        cmd += (["--type", kind] if kind else []) + [str(value)]
    _run(cmd)


def notify(change):
    """KGlobalSettings' change signal (fonts, cursor), as KDE's own settings send it."""
    _run(["dbus-send", "--session", "--type=signal", "/KGlobalSettings", "org.kde.KGlobalSettings.notifyChange",
          f"int32:{change}", "int32:0"])


def load_state():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state), encoding="utf-8")


def with_size(font, size):
    """"Noto Sans,10,-1,5,50,0,0,0,0,0" with another point size."""
    parts = font.split(",")
    if len(parts) < 2:
        parts = (font or "Noto Sans").split(",")[:1] + ["10"]
    parts[1] = str(size)
    return ",".join(parts)


def set_text_scale(percent):
    for group, key, base, default in FONTS:
        write("kdeglobals", group, key, with_size(read("kdeglobals", group, key, default), round(base * percent / 100)))
    notify(FONT_CHANGED)


def cursor_size():
    try:
        return int(read("kcminputrc", "Mouse", "cursorSize", "24") or 24)
    except ValueError:
        return 24


def set_cursor_size(size):
    """The size is always written here: plasma-apply-cursortheme with the theme already in use says so and succeeds
    without saving the new size (the HP test of 2026-11-09: no change even after signing in again). It still runs, to
    show the size at once where it can; everywhere else it shows after signing in again."""
    write("kcminputrc", "Mouse", "cursorSize", size, "int")
    theme = read("kcminputrc", "Mouse", "cursorTheme", "breeze_cursors") or "breeze_cursors"
    _run(["plasma-apply-cursortheme", "--size", str(size), theme])
    notify(CURSOR_CHANGED)


def sign_out():
    """Plasma's sign-out window (the user can still change their mind there)."""
    _run(["dbus-send", "--session", "--type=method_call", "--dest=org.kde.LogoutPrompt", "/LogoutPrompt",
          "org.kde.LogoutPrompt.promptLogout"])


def screen_reader_running():
    r = _run(["pgrep", "-x", "orca"])
    return bool(r) and r.returncode == 0


def set_screen_reader(on):
    write("kaccessrc", "ScreenReader", "Enabled", "true" if on else "false", "bool")
    _run(["kaccess"])  # the running kaccess reads its settings again (it starts or stops Orca)
    if on and not screen_reader_running():
        subprocess.Popen(["orca", "--replace"], start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    elif not on:
        _run(["pkill", "-x", "orca"])


def reconfigure_kwin():
    _run(["dbus-send", "--session", "--type=method_call", "--dest=org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure"])


class AccessibilityController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = load_state()
        self._sign_out = False  # the text or pointer size was changed: it shows everywhere after signing in again
        self.refresh()

    textScales = Property("QVariantList", lambda self: list(TEXT_SCALES), constant=True)
    cursorSizes = Property("QVariantList", lambda self: list(CURSOR_SIZES), constant=True)
    textScale = Property(int, lambda self: self._text, notify=changed)
    cursorSize = Property(int, lambda self: self._cursor, notify=changed)
    highContrast = Property(bool, lambda self: self._contrast, notify=changed)
    reduceMotion = Property(bool, lambda self: self._motion, notify=changed)
    screenReader = Property(bool, lambda self: self._reader, notify=changed)
    magnifier = Property(bool, lambda self: self._zoom, notify=changed)
    stickyKeys = Property(bool, lambda self: self._sticky, notify=changed)
    signOutNeeded = Property(bool, lambda self: self._sign_out, notify=changed)

    @Slot()
    def signOut(self):
        sign_out()

    @Slot()
    def refresh(self):
        scale = self._state.get("textScale", 100)
        self._text = scale if scale in TEXT_SCALES else 100
        size = cursor_size()
        self._cursor = min(CURSOR_SIZES, key=lambda s: abs(s - size))
        self._contrast = read("kdeglobals", "General", "ColorScheme") == CONTRAST_SCHEME
        self._motion = read("kdeglobals", "KDE", "AnimationDurationFactor", "1") in ("0", "0.0")
        self._reader = read("kaccessrc", "ScreenReader", "Enabled", "false") == "true"
        self._zoom = read("kwinrc", "Plugins", "zoomEnabled", "false") == "true"
        self._sticky = read("kaccessrc", "Keyboard", "StickyKeys", "false") == "true"
        self.changed.emit()

    @Slot(int)
    def setTextScale(self, percent):
        if percent in TEXT_SCALES:
            set_text_scale(percent)
            self._state["textScale"] = percent
            save_state(self._state)
            self._sign_out = True
        self.refresh()

    @Slot(int)
    def setCursorSize(self, size):
        if size in CURSOR_SIZES:
            set_cursor_size(size)
            self._sign_out = True
        self.refresh()

    @Slot(bool)
    def setHighContrast(self, on):
        if on and not self._contrast:
            self._state["schemeBefore"] = read("kdeglobals", "General", "ColorScheme", DEFAULT_SCHEME) or DEFAULT_SCHEME
            save_state(self._state)
            _run(["plasma-apply-colorscheme", CONTRAST_SCHEME])
        elif not on and self._contrast:
            before = self._state.pop("schemeBefore", "") or DEFAULT_SCHEME
            save_state(self._state)
            _run(["plasma-apply-colorscheme", before if before != CONTRAST_SCHEME else DEFAULT_SCHEME])
        self.refresh()

    @Slot(bool)
    def setReduceMotion(self, on):
        write("kdeglobals", "KDE", "AnimationDurationFactor", 0 if on else None)
        self.refresh()

    @Slot(bool)
    def setScreenReader(self, on):
        set_screen_reader(on)
        self.refresh()

    @Slot(bool)
    def setMagnifier(self, on):
        write("kwinrc", "Plugins", "zoomEnabled", "true" if on else "false", "bool")
        reconfigure_kwin()
        self.refresh()

    @Slot(bool)
    def setStickyKeys(self, on):
        write("kaccessrc", "Keyboard", "StickyKeys", "true" if on else "false", "bool")
        _run(["kaccess"])
        self.refresh()

    @Slot()
    def openKdeSettings(self):
        subprocess.Popen(["systemsettings", "kcm_access"], start_new_session=True)
