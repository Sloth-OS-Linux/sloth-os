"""Parental controls in a child's own session (the system side: /usr/libexec/sloth-os/screen-time, sloth-helper-family).

It runs in every account's session (sloth-family-session.path / .service): at sign-in and whenever the state files
in /run/sloth-os/family change. For an account without parental controls it does nothing (it only cleans up after
itself).
  - Screen time: the warnings (10, 5 and 1 minutes left, time's up) as notifications and as a banner at the top of
    the screen above everything, full-screen games and videos too (a layer-shell surface on the overlay layer; a
    notification stays behind a full-screen window). "Ask for more time" (malcontent-timerd's RequestExtension: a
    parent types their password in the window that comes up) only when the system side offers it: for the daily
    limit inside the allowed hours, not for the end of the hours. Signing out is done by the system side, not
    here: the child could stop this.
  - Blocked apps: they are hidden from the menus (a Hidden=true entry of our own in ~/.local/share/applications);
    Flatpak would not start them anyway (malcontent's app filter).
Start: python3 -m sloth_center.family_session [show <message> | banner <message>]
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .i18n import N_, tr

# shown by the sign-in screen when a child has no screen time now (/usr/libexec/sloth-os/screen-time --may-sign-in,
# which reads Sloth Center's translations), followed by when_again()'s sentence
SIGN_IN_REFUSED = N_("Your screen time is over for now.")

STATE_DIR = Path(os.environ.get("SLOTH_FAMILY_STATE", "/run/sloth-os/family"))
USER = os.environ.get("USER") or os.getlogin()
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SEEN = RUNTIME / "sloth-family-seen.json"       # the stage last shown, and the notification's process and number
APPS_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
MARK = "X-Sloth-Parental-Controls=hidden"
EXPORTS = [Path("/var/lib/flatpak/exports/share/applications"),
           Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "flatpak/exports/share/applications"]
EXTENSION = 30 * 60  # "Ask for more time" asks for half an hour


def _clock(ts):
    """A time in the user's own format (16:00, 4:00 PM); "tomorrow at" etc. are added around it."""
    try:
        from PySide6.QtCore import QDateTime, QLocale
        return QLocale().toString(QDateTime.fromSecsSinceEpoch(int(ts)).time(), QLocale.FormatType.ShortFormat)
    except Exception:
        return time.strftime("%H:%M", time.localtime(ts))


def when_again(ts):
    """When the child can use the computer again: "at 16:00", "tomorrow at 16:00" or "tomorrow"."""
    then, today = time.localtime(ts), time.localtime()
    days = (time.mktime((then.tm_year, then.tm_mon, then.tm_mday, 0, 0, 0, 0, 0, -1))
            - time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    if round(days) <= 0:
        return tr("You can use the computer again at {time}.", time=_clock(ts))
    if round(days) == 1:
        if then.tm_hour == 0 and then.tm_min == 0:
            return tr("You can use the computer again tomorrow.")
        return tr("You can use the computer again tomorrow at {time}.", time=_clock(ts))
    return ""


def message(state, previous):
    """(title, text, with "Ask for more time") for a stage, or None if there is nothing to say."""
    stage, end = state.get("stage"), state.get("end", 0)
    ask = bool(state.get("ask", True))
    if stage in ("10", "5", "1"):
        minutes = int(stage)
        text = tr("{n} minutes of screen time left today. At {time} you'll be signed out, so save your work.",
                  n=minutes, time=_clock(end)) if minutes > 1 else \
            tr("1 minute of screen time left today. Save your work now.")
        return tr("Screen time"), text, ask
    if stage == "up":
        text = tr("Your screen time is over for now. You'll be signed out in a minute, so save your work now.")
        again = when_again(state.get("next", 0)) if state.get("next") else ""
        return tr("Time's up"), (text + " " + again).strip(), ask
    if stage == "ok" and previous.get("stage") in ("10", "5", "1", "up") and end > previous.get("end", 0):
        return tr("Screen time"), tr("You got more time: you can use the computer until {time}.", time=_clock(end)), False
    return None


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def _close_previous(seen):
    """The previous notification's process stops waiting for a click (its notification is replaced), and the
    previous banner goes."""
    for pid in (seen.get("pid"), seen.get("banner")):
        if isinstance(pid, int) and pid > 1:
            try:
                if "family_session" in Path(f"/proc/{pid}/cmdline").read_text(errors="replace"):
                    os.kill(pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass


def screen_time():
    state = _read_json(STATE_DIR / f"{USER}.json")
    seen = _read_json(SEEN)
    if not state:
        if seen:  # the limit was taken off, or a new session: start again
            SEEN.unlink(missing_ok=True)
        return
    if state.get("stage") == seen.get("stage") and state.get("end") == seen.get("end"):
        return
    msg = message(state, seen)
    _close_previous(seen)
    seen.update({"stage": state.get("stage"), "end": state.get("end"), "pid": None, "banner": None})
    if msg:
        proc = subprocess.Popen([sys.executable, "-m", "sloth_center.family_session", "show", json.dumps(msg)],
                                start_new_session=True)
        seen["pid"] = proc.pid
        # every window of the banner's process is a layer-shell surface (above full-screen windows)
        proc = subprocess.Popen([sys.executable, "-m", "sloth_center.family_session", "banner", json.dumps(msg)],
                                start_new_session=True, env={**os.environ, "QT_WAYLAND_SHELL_INTEGRATION": "layer-shell",
                                                              "QT_QUICK_CONTROLS_STYLE": "Fusion"})
        seen["banner"] = proc.pid
    SEEN.write_text(json.dumps(seen))


def show(msg):
    """One notification (in its own process: it waits for the click)."""
    title, text, ask = json.loads(msg)
    seen = _read_json(SEEN)
    replace = [f"--replace-id={seen['id']}"] if isinstance(seen.get("id"), int) else []
    actions = ["--action=more=" + tr("Ask for more time")] if ask else []
    try:
        proc = subprocess.Popen(["notify-send", "--app-name=Sloth OS", "--icon=preferences-desktop-user-password",
                                 "--urgency=critical", "--expire-time=0", "--print-id", *replace, *actions, title,
                                 text], stdout=subprocess.PIPE, text=True)
    except OSError:
        return 0
    first = proc.stdout.readline().strip()
    if first.isdigit():
        seen = _read_json(SEEN)
        seen["id"] = int(first)
        SEEN.write_text(json.dumps(seen))
    choice = proc.stdout.readline().strip()
    proc.wait()
    if choice == "more":
        ask_for_more_time()
    return 0


BANNER_QML = """
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window
import org.kde.layershell as LayerShell

// No Kirigami (nor KDE's controls style, which loads it) here: it hung where nothing else did (2026-11-06)
Window {
    id: win
    readonly property int gap: Math.round(fontMetrics.height * 0.6)
    width: Math.min(Screen.width - 2 * gap, fontMetrics.height * 34)
    height: box.implicitHeight + 4 * gap
    color: "transparent"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityNone
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.scope: "sloth-screen-time"
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }
    FontMetrics { id: fontMetrics }
    Rectangle {
        anchors.fill: parent
        anchors.margins: win.gap
        radius: win.gap
        color: palette.window
        border.color: "#da4453"
        border.width: 3
        ColumnLayout {
            id: box
            anchors.fill: parent
            anchors.margins: win.gap
            spacing: Math.round(win.gap / 2)
            QQC2.Label {
                text: banner.title_
                color: palette.windowText
                font.bold: true
                font.pointSize: fontMetrics.font.pointSize * 1.4
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }
            QQC2.Label { text: banner.text_; color: palette.windowText; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                QQC2.Button { visible: banner.ask_; text: banner.askText; onClicked: banner.askMore() }
                QQC2.Button { text: banner.okText; onClicked: Qt.quit() }
            }
        }
    }
    Timer { interval: banner.timeout; running: banner.timeout > 0; onTriggered: Qt.quit() }
}
"""


def banner(msg):
    """The warning at the top of the screen, above full-screen windows; a warning goes after 30 seconds, "time's up"
    stays until the sign-out. Without layer-shell support (or a Wayland session) only the notification is there."""
    title, text, ask = json.loads(msg)
    try:
        from PySide6.QtCore import Property, QObject, Slot
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError:
        return 0

    class Banner(QObject):
        def __init__(self):
            super().__init__()
            self._asked = False

        title_ = Property(str, lambda self: title, constant=True)
        text_ = Property(str, lambda self: text, constant=True)
        ask_ = Property(bool, lambda self: bool(ask), constant=True)
        askText = Property(str, lambda self: tr("Ask for more time"), constant=True)
        okText = Property(str, lambda self: tr("OK"), constant=True)
        timeout = Property(int, lambda self: 0 if title == tr("Time's up") else 30000, constant=True)

        @Slot()
        def askMore(self):
            app.quit()
            ask_for_more_time()

    # KDE's own controls style hung where Fusion did not (2026-11-06; QQuickStyle.setStyle was not enough)
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Fusion"
    app = QGuiApplication([sys.argv[0]])
    model = Banner()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("banner", model)
    engine.loadData(BANNER_QML.encode())
    if not engine.rootObjects():
        return 0
    engine.rootObjects()[0].show()
    app.exec()
    return 0


def ask_for_more_time():
    """malcontent-timerd asks a parent (the password window of the extension agent, in this session)."""
    r = subprocess.run(["busctl", "--system", "call", "--timeout=600", "org.freedesktop.MalcontentTimer1",
                        "/org/freedesktop/MalcontentTimer1", "org.freedesktop.MalcontentTimer1.Child",
                        "RequestExtension", "ssta{sv}", "login-session", "", str(EXTENSION), "0"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["notify-send", "--app-name=Sloth OS", "--icon=dialog-error", tr("Screen time"),
                        tr("Couldn't ask for more time. Ask a parent to sign in and change your screen time in "
                           "Sloth Center.")], capture_output=True)


# --- Blocked apps ---------------------------------------------------------------------------------------

def _app_filter():
    """This account's app filter (malcontent; reading your own needs no password), or None."""
    try:
        import gi
        gi.require_version("Malcontent", "0")
        from gi.repository import Gio, Malcontent
        manager = Malcontent.Manager.new(Gio.bus_get_sync(Gio.BusType.SYSTEM, None))
        return manager.get_app_filter(os.getuid(), Malcontent.ManagerGetValueFlags.NONE, None)
    except Exception:
        return None


def _flatpak_entries():
    """{desktop file name: Flatpak app ID} of the installed apps."""
    out = {}
    for folder in EXPORTS:
        for path in folder.glob("*.desktop"):
            app = ""
            try:
                for line in path.read_text(errors="replace").splitlines():
                    if line.startswith("X-Flatpak="):
                        app = line.split("=", 1)[1].strip()
                        break
            except OSError:
                continue
            if app:
                out[path.name] = app
    return out


def hide_blocked_apps():
    app_filter = _app_filter()
    blocked = set()
    if app_filter is not None:
        blocked = {name for name, app in _flatpak_entries().items()
                   if not app_filter.is_flatpak_app_allowed(app)}
    changed = False
    for name in blocked:
        path = APPS_DIR / name
        if path.exists():
            continue  # the user's own entry: not touched
        APPS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(f"[Desktop Entry]\nType=Application\nName={name}\nHidden=true\n{MARK}\n")
        changed = True
    for path in APPS_DIR.glob("*.desktop") if APPS_DIR.is_dir() else []:
        try:
            ours = MARK in path.read_text(errors="replace")
        except OSError:
            continue
        if ours and path.name not in blocked:
            path.unlink()
            changed = True
    if changed:
        subprocess.run(["kbuildsycoca6"], capture_output=True)


def main(argv):
    if argv[:1] == ["show"] and len(argv) == 2:
        return show(argv[1])
    if argv[:1] == ["banner"] and len(argv) == 2:
        return banner(argv[1])
    if not STATE_DIR.is_dir() and not SEEN.exists():
        hide_blocked_apps()  # also cleans up after an account that had parental controls before
        return 0
    screen_time()
    hide_blocked_apps()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
