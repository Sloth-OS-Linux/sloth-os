"""Wi-Fi and network (the first row of Sloth Center's sidebar; WifiPage.qml): the Wi-Fi networks around, connect,
disconnect, forget, Wi-Fi on and off, and the wired connection. Everything else (VPN, a fixed address, company and
school networks with a user name, hidden networks) is in KDE's network window: "More settings".

Read with nmcli (NetworkManager). A new network's password goes to NetworkManager over D-Bus
(AddAndActivateConnection, with the access point, so NetworkManager fills in the rest: WPA2, WPA3…), never on a
command line, where every account on the computer could read it. A network that does not connect with the password
given is not kept (wrong password: the same question next time, no broken saved network).
"""
import logging
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from . import kde_settings

log = logging.getLogger("sloth-center.network")

NM = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
CONNECT_WAIT = 40   # seconds for a network to connect (DHCP on a busy network can be slow)
REFRESH = 10000     # ms between two looks at the networks while the page is open


def _nmcli(args, timeout=20):
    """(ok, output) of `nmcli args`."""
    try:
        r = subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout if r.returncode == 0 else r.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("nmcli %s: %s", " ".join(args[:3]), e)
        return False, str(e)


def split_terse(line):
    """A line of `nmcli -t`: fields split on ":" (in a field, ":" and "\\" come escaped with "\\")."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def security_kind(security):
    """"open", "personal" (a password: WPA, WPA2, WPA3) or "enterprise" (a user name too, or WEP: KDE's window)."""
    s = (security or "").strip().replace("--", "")
    if not s:
        return "open"
    if "802.1X" in s or "WEP" in s:
        return "enterprise"
    return "personal"


def parse_networks(text, saved=()):
    """`nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY dev wifi list` → one row per network name (the strongest of its
    access points), the connected one first, then by signal. Hidden networks (no name) are left out."""
    best = {}
    for line in text.splitlines():
        f = split_terse(line)
        if len(f) < 4 or not f[1]:
            continue
        inuse, ssid, security = f[0].strip() == "*", f[1], f[3]
        try:
            signal = int(f[2])
        except ValueError:
            signal = 0
        old = best.get(ssid)
        if old is None or inuse or (not old["connected"] and signal > old["signal"]):
            best[ssid] = {"ssid": ssid, "signal": signal, "kind": security_kind(security),
                          "connected": inuse or bool(old and old["connected"]), "saved": ssid in saved}
    return sorted(best.values(), key=lambda n: (not n["connected"], not n["saved"], -n["signal"], n["ssid"].casefold()))


def parse_devices(text):
    """`nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device` → {"wifi": [{device, state, connection}], "ethernet": […]}."""
    out = {"wifi": [], "ethernet": []}
    for line in text.splitlines():
        f = split_terse(line)
        if len(f) >= 4 and f[1] in out:
            out[f[1]].append({"device": f[0], "state": f[2], "connection": f[3]})
    return out


def parse_saved(text):
    """`nmcli -t -f NAME,TYPE connection show` → the names of the saved Wi-Fi networks."""
    return {f[0] for f in map(split_terse, text.splitlines()) if len(f) >= 2 and f[1] == "802-11-wireless"}


def signal_icon(signal):
    level = "excellent" if signal >= 75 else "good" if signal >= 50 else "ok" if signal >= 25 else "low"
    return f"network-wireless-signal-{level}"


def read_state():
    """Everything the page shows, read now (in a thread: nmcli can take a moment)."""
    ok, radio = _nmcli(["radio", "wifi"])
    devices = parse_devices(_nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])[1])
    saved = parse_saved(_nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"])[1])
    networks = []
    wifi_on = ok and radio.strip() == "enabled"
    if devices["wifi"] and wifi_on:
        ok, text = _nmcli(["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"])
        if ok:
            networks = parse_networks(text, saved)
    for n in networks:
        n["icon"] = signal_icon(n["signal"])
    wired = devices["ethernet"]
    return {
        "hasWifi": bool(devices["wifi"]),
        "wifiOn": wifi_on,
        "networks": networks,
        "hasWired": bool(wired),
        "wiredConnected": any(d["state"] == "connected" for d in wired),
    }


def _wifi_device():
    ok, text = _nmcli(["-t", "-f", "DEVICE,TYPE", "device"])
    for f in map(split_terse, text.splitlines()):
        if len(f) >= 2 and f[1] == "wifi":
            return f[0]
    return None


def _device_state(device):
    """NetworkManager's state number of the device (100: connected, 120: failed, 30: disconnected…)."""
    ok, text = _nmcli(["-t", "-g", "GENERAL.STATE", "device", "show", device])
    try:
        return int(text.split()[0]) if ok and text else 0
    except ValueError:
        return 0


def _wait_connected(device, ssid):
    """"" once the device is connected to ssid; else why not: "password" (the network asked for the password again:
    the one given was wrong; NetworkManager would now ask through KDE's own window) or "failed"."""
    started = False
    for _ in range(CONNECT_WAIT):
        time.sleep(1)
        state = _device_state(device)
        if state == 100:
            ok, name = _nmcli(["-t", "-g", "GENERAL.CONNECTION", "device", "show", device])
            return "" if name.strip() == ssid or not ok else "failed"
        if state == 60:      # need auth: the password was given with the request, so this one was not accepted
            return "password"
        if 40 <= state < 100:
            started = True
        elif started and state in (30, 120):  # back to disconnected, or failed
            return "failed"
    return "failed"


def connect_new(ssid, password):
    """A network not saved yet: (ok, reason). reason: "" | "password" | "failed"."""
    try:
        from gi.repository import Gio, GLib
    except ImportError:
        return False, "failed"
    device = _wifi_device()
    if not device:
        return False, "failed"
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        def call(path, iface, method, args, reply):
            return bus.call_sync(NM, path, iface, method, args, GLib.VariantType(reply),
                                 Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 30000, None).unpack()

        dev_path = call(NM_PATH, NM, "GetDeviceByIpIface", GLib.Variant("(s)", (device,)), "(o)")[0]
        # the access point with this name and the strongest signal: NetworkManager fills in its security from it
        aps = call(dev_path, NM + ".Device.Wireless", "GetAllAccessPoints", None, "(ao)")[0]
        best, strength = None, -1
        for ap in aps:
            props = call(ap, "org.freedesktop.DBus.Properties", "GetAll",
                         GLib.Variant("(s)", (NM + ".AccessPoint",)), "(a{sv})")[0]
            if bytes(props.get("Ssid", b"")).decode("utf-8", "replace") == ssid and props.get("Strength", 0) > strength:
                best, strength = ap, props.get("Strength", 0)
        if best is None:
            return False, "failed"
        settings = {"connection": {"id": GLib.Variant("s", ssid)}}
        if password:
            settings["802-11-wireless-security"] = {"psk": GLib.Variant("s", password)}
        conn_path, _active = call(NM_PATH, NM, "AddAndActivateConnection",
                                  GLib.Variant("(a{sa{sv}}oo)", (settings, dev_path, best)), "(oo)")
    except Exception as e:  # noqa: BLE001 - a D-Bus error: NetworkManager said no
        log.warning("connecting to a new network: %s", e)
        return False, "failed"
    reason = _wait_connected(device, ssid)
    if not reason:
        return True, ""
    # not kept: a wrong password would otherwise stay saved, and the next try would not ask again; deleting it also
    # ends the attempt (and KDE's password window, if NetworkManager opened it)
    try:
        bus.call_sync(NM, conn_path, NM + ".Settings.Connection", "Delete", None, None,
                      Gio.DBusCallFlags.NONE, 10000, None)
    except Exception as e:  # noqa: BLE001
        log.warning("removing the failed network: %s", e)
    return False, reason if password else "failed"


class NetworkController(QObject):
    """QML (context property "network"): state, busy, connecting, error; refresh(), start(), stop(), setWifi(on),
    connectTo(ssid, password), disconnectWifi(), forget(ssid), openMore()."""
    changed = Signal()
    _read = Signal(dict)
    _done = Signal(str, bool, str)  # ssid, ok, reason

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = {"hasWifi": False, "wifiOn": False, "networks": [], "hasWired": False, "wiredConnected": False}
        self._busy = False
        self._loaded = False
        self._connecting = ""
        self._error = {}
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH)
        self._timer.timeout.connect(self.refresh)
        self._read.connect(self._on_read)
        self._done.connect(self._on_done)

    @Property("QVariantMap", notify=changed)
    def state(self):
        return self._state

    busy = Property(bool, lambda self: self._busy, notify=changed)
    loaded = Property(bool, lambda self: self._loaded, notify=changed)
    connecting = Property(str, lambda self: self._connecting, notify=changed)

    @Property("QVariantMap", notify=changed)
    def error(self):
        """{ssid, reason} of the last failed connection ("password" or "failed"), or {}."""
        return self._error

    @Slot()
    def start(self):
        self.refresh()
        self._timer.start()

    @Slot()
    def stop(self):
        self._timer.stop()

    @Slot()
    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()
        threading.Thread(target=lambda: self._read.emit(read_state()), daemon=True).start()

    def _on_read(self, state):
        self._state, self._busy, self._loaded = state, False, True
        self.changed.emit()

    @Slot()
    def rescan(self):
        def work():
            _nmcli(["device", "wifi", "rescan"])
            time.sleep(3)  # the adapter needs a moment to hear the networks
            self._read.emit(read_state())
        self._busy = True
        self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot(bool)
    def setWifi(self, on):
        def work():
            _nmcli(["radio", "wifi", "on" if on else "off"])
            if on:
                time.sleep(3)  # the adapter wakes up, then it needs a few seconds to hear the networks
                _nmcli(["device", "wifi", "rescan"])
                time.sleep(4)
            self._read.emit(read_state())
        self._busy = True
        self.changed.emit()
        threading.Thread(target=work, daemon=True).start()

    @Slot(str, str)
    def connectTo(self, ssid, password):
        """A saved network (password ""), or a new one with its password ("" for an open network)."""
        if self._connecting:
            return
        saved = any(n["ssid"] == ssid and n["saved"] for n in self._state["networks"])
        self._connecting, self._error = ssid, {}
        self.changed.emit()

        def work():
            if saved:
                ok, _ = _nmcli(["connection", "up", "id", ssid], timeout=CONNECT_WAIT + 5)
                self._done.emit(ssid, ok, "" if ok else "failed")
            else:
                ok, reason = connect_new(ssid, password)
                self._done.emit(ssid, ok, reason)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, ssid, ok, reason):
        self._connecting = ""
        self._error = {} if ok else {"ssid": ssid, "reason": reason}
        self.changed.emit()
        self.refresh()

    @Slot()
    def disconnectWifi(self):
        device = next((d["device"] for d in parse_devices(
            _nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"])[1])["wifi"]), None)
        if device:
            threading.Thread(target=lambda: (_nmcli(["device", "disconnect", device]),
                                             self._read.emit(read_state())), daemon=True).start()

    @Slot(str)
    def forget(self, ssid):
        threading.Thread(target=lambda: (_nmcli(["connection", "delete", "id", ssid]),
                                         self._read.emit(read_state())), daemon=True).start()

    @Slot()
    def openMore(self):
        """KDE's network window: VPN, a fixed address, company networks, hidden networks…"""
        kde_settings.open_page("kcm_networkmanagement")
