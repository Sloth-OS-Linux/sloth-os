"""Vékony aszinkron kliens az rpm-ostree rendszerszolgáltatás D-Bus felületéhez.

Parancssort nem futtatunk: minden a D-Bus API-n megy, ami folyamatjelzést
(százalék, éppen futó lépés, letöltött adat) is ad. A jogosultságot igénylő
hívásoknál a polkit grafikus jelszókérő ablakot mutat.

A GLib callbackek a Qt eseményhurkában futnak (a Qt Linuxon a GLib
eseménykezelőjét használja), így nincs szükség külön szálra.
"""
from gi.repository import Gio, GLib

BUS_NAME = "org.projectatomic.rpmostree1"
SYSROOT_PATH = "/org/projectatomic/rpmostree1/Sysroot"
SYSROOT_IFACE = BUS_NAME + ".Sysroot"
OS_IFACE = BUS_NAME + ".OS"
TXN_IFACE = BUS_NAME + ".Transaction"

# A polkit jelszókérő ablak miatt a hívás sokáig tarthat
CALL_TIMEOUT_MS = GLib.MAXINT
INTERACTIVE = Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION


def _asv(d):
    """Python dict -> a{sv} GLib.Variant."""
    out = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = GLib.Variant("b", v)
        elif isinstance(v, int):
            out[k] = GLib.Variant("i", v)
        else:
            out[k] = GLib.Variant("s", str(v))
    return out


class Transaction:
    """Egy futó rpm-ostree tranzakció: privát D-Bus kapcsolat, jelzések."""

    def __init__(self, address, on_task, on_percent, on_download, on_finished):
        self._on_task = on_task
        self._on_percent = on_percent
        self._on_download = on_download
        self._on_finished = on_finished
        self._conn = None
        Gio.DBusConnection.new_for_address(
            address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT, None, None, self._connected)

    def _connected(self, _src, res):
        try:
            self._conn = Gio.DBusConnection.new_for_address_finish(res)
        except GLib.Error as e:
            self._on_finished(False, e.message)
            return
        self._conn.signal_subscribe(None, TXN_IFACE, None, "/", None,
                                    Gio.DBusSignalFlags.NONE, self._signal)
        self._conn.call(None, "/", TXN_IFACE, "Start", None, GLib.VariantType("(b)"),
                        Gio.DBusCallFlags.NONE, -1, None, self._started)

    def _started(self, conn, res):
        try:
            conn.call_finish(res)
        except GLib.Error as e:
            self._on_finished(False, e.message)

    def _signal(self, _conn, _sender, _path, _iface, name, params):
        args = params.unpack()
        if name in ("TaskBegin", "Message"):
            self._on_task(args[0])
        elif name == "PercentProgress":
            self._on_task(args[0])
            self._on_percent(int(args[1]))
        elif name == "DownloadProgress":
            # transfer: (letöltött bájtok, bájt/mp)
            transferred, rate = args[5]
            self._on_download(int(transferred), int(rate))
        elif name == "Finished":
            self._on_finished(bool(args[0]), args[1])

    def cancel(self):
        if self._conn:
            self._conn.call(None, "/", TXN_IFACE, "Cancel", None, None,
                            Gio.DBusCallFlags.NONE, -1, None, None)


class RpmOstree:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.sysroot = Gio.DBusProxy.new_sync(
            self.bus, Gio.DBusProxyFlags.NONE, None, BUS_NAME, SYSROOT_PATH, SYSROOT_IFACE, None)
        self.sysroot.call_sync("RegisterClient", GLib.Variant("(a{sv})", (_asv({"id": "sloth-center"}),)),
                               Gio.DBusCallFlags.NONE, -1, None)
        os_path = self.sysroot.get_cached_property("Booted").unpack()
        self.os = Gio.DBusProxy.new_sync(
            self.bus, Gio.DBusProxyFlags.NONE, None, BUS_NAME, os_path, OS_IFACE, None)

    # --- Állapot -----------------------------------------------------------

    def _prop(self, proxy, name, default=None):
        v = proxy.get_cached_property(name)
        return v.unpack() if v is not None else default

    def reload(self):
        self.sysroot.call_sync("Reload", None, Gio.DBusCallFlags.NONE, -1, None)

    def booted(self):
        return self._prop(self.os, "BootedDeployment", {})

    def default(self):
        return self._prop(self.os, "DefaultDeployment", {})

    def rollback_target(self):
        return self._prop(self.os, "RollbackDeployment", {})

    def deployments(self):
        """Az összes telepített verzió, az ostree sorrendjében (a pin index ehhez igazodik)."""
        return self._prop(self.sysroot, "Deployments", []) or []

    def cached_update(self):
        return self._prop(self.os, "CachedUpdate", {})

    def active_transaction_address(self):
        return self._prop(self.sysroot, "ActiveTransactionPath", "")

    def connect_changed(self, callback):
        """A callback meghívódik, ha a rendszer állapota változik (pl. a háttérben frissült)."""
        self.sysroot.connect("g-properties-changed", lambda *a: callback())
        self.os.connect("g-properties-changed", lambda *a: callback())

    # --- Műveletek (mind tranzakciót indít, a címet adja vissza) -----------

    def _start(self, method, params, out_type, on_address, on_error):
        def done(proxy, res):
            try:
                address = proxy.call_finish(res).unpack()[-1]
            except GLib.Error as e:
                on_error(e.message)
                return
            on_address(address)
        self.os.call(method, params, INTERACTIVE, CALL_TIMEOUT_MS, None, done)

    def check_update(self, on_address, on_error):
        # Mint az "rpm-ostree upgrade --check": csak megnézi, van-e új verzió
        self._start("AutomaticUpdateTrigger",
                    GLib.Variant("(a{sv})", (_asv({"mode": "check", "output-to-self": False}),)),
                    "(bs)", on_address, on_error)

    def upgrade(self, on_address, on_error):
        self._start("UpdateDeployment",
                    GLib.Variant("(a{sv}a{sv})", ({}, _asv({"initiating-command-line": "Sloth Központ: frissítés"}))),
                    "(s)", on_address, on_error)

    def rollback(self, on_address, on_error):
        self._start("Rollback", GLib.Variant("(a{sv})", (_asv({"reboot": False}),)),
                    "(s)", on_address, on_error)

    def rebase(self, refspec, on_address, on_error):
        """Váltás másik image-re (pl. NVIDIA-s változat). A csomagrétegek megmaradnak."""
        self._start("Rebase", GLib.Variant("(a{sv}sas)", (_asv({"reboot": False}), refspec, [])),
                    "(s)", on_address, on_error)

    def kernel_args_string(self):
        """A következő indításkor használt kernelparaméterek (egy szövegként)."""
        try:
            cfg = self.os.call_sync("GetDeploymentBootConfig", GLib.Variant("(sb)", ("", False)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            return cfg.get("options", "")
        except GLib.Error:
            return ""

    def set_kernel_args(self, added, removed, on_address, on_error):
        existing = self.kernel_args_string()
        self._start("KernelArgs", GLib.Variant("(sasasasa{sv})", (existing, added, [], removed,
                    _asv({"initiating-command-line": "Sloth Központ: kernelparaméterek"}))),
                    "(s)", on_address, on_error)

    def layered_packages(self):
        d = self.default() or self.booted()
        return sorted(set(d.get("requested-packages", []) or []))

    def pkg_change(self, added, removed, on_address, on_error):
        self._start("PkgChange", GLib.Variant("(a{sv}asas)", (_asv({"reboot": False}), added, removed)),
                    "(s)", on_address, on_error)
