"""Sloth Center in one window only: starting it again brings the open window forward.

The first Sloth Center owns the session bus name org.slothos.Center. A later start (the Start menu, a notification's
button, `systemsettings <page>` through /usr/libexec/sloth-os/systemsettings-wrapper) finds the name taken, hands its
request over (Open: the page, the KDE page and its arguments, the game) and quits; the open window shows that page
and comes forward. If the open one does not answer (it hangs, or it is still starting), the later start opens a
window of its own as before: Sloth Center always opens.

Coming forward on Wayland: KWin lets a window take the focus with an activation token. The Start menu gives the
new process one (XDG_ACTIVATION_TOKEN); it is handed over too, and Qt's QWindow.requestActivate() uses the token in
the environment (qtwayland's xdg-shell). Without a token the taskbar entry asks for attention instead.
"""
import logging
import os

from gi.repository import Gio, GLib
from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

NAME = "org.slothos.Center"
PATH = "/org/slothos/Center"
IFACE = "org.slothos.Center"
XML = f"""<node>
  <interface name="{IFACE}">
    <method name="Open">
      <arg name="page" type="s" direction="in"/>
      <arg name="kcm" type="s" direction="in"/>
      <arg name="kcm_args" type="s" direction="in"/>
      <arg name="game" type="s" direction="in"/>
      <arg name="activation_token" type="s" direction="in"/>
    </method>
  </interface>
</node>"""
# org.freedesktop.DBus.RequestName: flags and answers
_DO_NOT_QUEUE = 4
_PRIMARY_OWNER, _EXISTS, _ALREADY_OWNER = 1, 3, 4
# The connection that owns the name: kept for the whole run (GIO keeps its shared connection only weakly; dropped,
# it closes and the name goes with it)
_bus = None


def claim_or_forward(page, kcm, kcm_args, game):
    """True: another Sloth Center took the request (this one quits). False: this is the one (or the bus is not
    usable, or the other one did not answer): open the window here."""
    global _bus
    try:
        conn = _bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        answer = conn.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                "RequestName", GLib.Variant("(su)", (NAME, _DO_NOT_QUEUE)),
                                GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
    except GLib.Error as e:
        log.warning("one window: the session bus is not usable (%s)", e.message)
        return False
    if answer in (_PRIMARY_OWNER, _ALREADY_OWNER):
        return False
    token = os.environ.get("XDG_ACTIVATION_TOKEN", "")
    try:
        conn.call_sync(NAME, PATH, IFACE, "Open", GLib.Variant("(sssss)", (page, kcm, kcm_args, game, token)),
                       None, Gio.DBusCallFlags.NONE, 10000, None)
        return True
    except GLib.Error as e:
        log.warning("one window: the open Sloth Center did not answer (%s); opening another window", e.message)
        return False


class SingleInstance(QObject):
    """Receives the later starts' requests: openRequested → Main.qml. Made right after claiming the name; the calls
    wait on the bus until Qt's (GLib's) event loop runs, by then the window and its handlers are there."""
    openRequested = Signal(str, str, str, str)    # page, kcm, kcm_args, game

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reg = 0
        try:
            self._conn = _bus or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            node = Gio.DBusNodeInfo.new_for_xml(XML)
            self._reg = self._conn.register_object(PATH, node.interfaces[0], self._on_call, None, None)
        except GLib.Error as e:
            log.warning("one window: cannot listen on the session bus (%s)", e.message)

    def _on_call(self, _conn, _sender, _path, _iface, method, params, invocation):
        if method != "Open":
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
            return
        page, kcm, kcm_args, game, token = params.unpack()
        invocation.return_value(None)                 # at once: the later start may quit
        log.info("started again: page=%r kcm=%r game=%r token=%s", page, kcm, game, "yes" if token else "no")
        old = os.environ.get("XDG_ACTIVATION_TOKEN")
        if token:
            os.environ["XDG_ACTIVATION_TOKEN"] = token
        try:
            self.openRequested.emit(page, kcm, kcm_args, game)   # Main.qml raises the window (requestActivate)
        finally:
            if token:
                if old is None:
                    os.environ.pop("XDG_ACTIVATION_TOKEN", None)
                else:
                    os.environ["XDG_ACTIVATION_TOKEN"] = old
