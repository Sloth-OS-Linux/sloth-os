"""A thin asynchronous client for the D-Bus interface of the rpm-ostree system service.

We do not run command lines: everything goes through the D-Bus API, which also gives progress
(percentage, the step running now, downloaded data). For calls that need permission,
polkit shows a graphical password window.

The GLib callbacks run in Qt's event loop (on Linux Qt uses GLib's
event dispatcher), so no separate thread is needed.
"""
from gi.repository import Gio, GLib

BUS_NAME = "org.projectatomic.rpmostree1"
SYSROOT_PATH = "/org/projectatomic/rpmostree1/Sysroot"
SYSROOT_IFACE = BUS_NAME + ".Sysroot"
OS_IFACE = BUS_NAME + ".OS"
TXN_IFACE = BUS_NAME + ".Transaction"

# Because of polkit's password window the call may take long
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
    """A running rpm-ostree transaction: a private D-Bus connection, signals."""

    def __init__(self, address, on_task, on_percent, on_download, on_finished):
        self._on_task = on_task
        self._on_percent = on_percent
        self._on_download = on_download
        self._on_finished = on_finished
        self._conn = None
        self._sub = 0
        Gio.DBusConnection.new_for_address(
            address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT, None, None, self._connected)

    def _connected(self, _src, res):
        try:
            self._conn = Gio.DBusConnection.new_for_address_finish(res)
        except GLib.Error as e:
            self._on_finished(False, e.message)
            return
        self._sub = self._conn.signal_subscribe(None, TXN_IFACE, None, "/", None,
                                                Gio.DBusSignalFlags.NONE, self._signal)
        self._conn.call(None, "/", TXN_IFACE, "Start", None, GLib.VariantType("(b)"),
                        Gio.DBusCallFlags.NONE, -1, None, self._started)

    def _started(self, conn, res):
        try:
            conn.call_finish(res)
        except GLib.Error as e:
            self._close()
            self._on_finished(False, e.message)

    def _signal(self, _conn, _sender, _path, _iface, name, params):
        args = params.unpack()
        if name in ("TaskBegin", "Message"):
            self._on_task(args[0])
        elif name == "PercentProgress":
            self._on_task(args[0])
            self._on_percent(int(args[1]))
        elif name == "DownloadProgress":
            # transfer: (downloaded bytes, bytes/s)
            transferred, rate = args[5]
            self._on_download(int(transferred), int(rate))
        elif name == "Finished":
            self._close()
            self._on_finished(bool(args[0]), args[1])

    def _close(self):
        """We close the connection at the end of the transaction, as the rpm-ostree command does too. If it stays open,
        the service forcibly closes it after 30 s ("Forcibly closing transaction due to timeout"), and a new operation
        starting right then (e.g. an update) may crash (2026-10-20, real machine: rpm-ostree core dump
        in deploy_transaction_execute, the download was interrupted)."""
        if not self._conn:
            return
        conn, self._conn = self._conn, None
        if self._sub:
            conn.signal_unsubscribe(self._sub)
            self._sub = 0
        conn.close(None, None, None)

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

    # --- State -----------------------------------------------------------

    def _prop(self, proxy, name, default=None):
        """Always asks the service, not the proxy's cache: the cache only updates with the
        PropertiesChanged signal, which after a check / update came late or not at all, so until
        Sloth Center was reopened it showed the old state ("no update", a missing restart)."""
        try:
            v = proxy.call_sync("org.freedesktop.DBus.Properties.Get",
                                GLib.Variant("(ss)", (proxy.get_interface_name(), name)),
                                Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
            return v if v is not None else default
        except GLib.Error:
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
        """Every installed version, in ostree's order (the pin index follows it)."""
        return self._prop(self.sysroot, "Deployments", []) or []

    def cached_update(self):
        return self._prop(self.os, "CachedUpdate", {})

    def active_transaction_address(self):
        return self._prop(self.sysroot, "ActiveTransactionPath", "")

    def connect_changed(self, callback):
        """The callback is called when the system's state changes (e.g. it updated in the background)."""
        self.sysroot.connect("g-properties-changed", lambda *a: callback())
        self.os.connect("g-properties-changed", lambda *a: callback())

    # --- Operations (each starts a transaction and returns its address) -----------

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
        # Like "rpm-ostree upgrade --check": only checks whether there is a new version
        self._start("AutomaticUpdateTrigger",
                    GLib.Variant("(a{sv})", (_asv({"mode": "check", "output-to-self": False}),)),
                    "(bs)", on_address, on_error)

    def upgrade(self, on_address, on_error):
        self._start("UpdateDeployment",
                    GLib.Variant("(a{sv}a{sv})", ({}, _asv({"initiating-command-line": "Sloth Center: update"}))),
                    "(s)", on_address, on_error)

    def rollback(self, on_address, on_error):
        self._start("Rollback", GLib.Variant("(a{sv})", (_asv({"reboot": False}),)),
                    "(s)", on_address, on_error)

    def rebase(self, refspec, on_address, on_error):
        """Switches to another image (e.g. the NVIDIA version). The package layers stay."""
        self._start("Rebase", GLib.Variant("(a{sv}sas)", (_asv({"reboot": False}), refspec, [])),
                    "(s)", on_address, on_error)

    def kernel_args_string(self):
        """The kernel parameters used at the next start (as one text)."""
        try:
            cfg = self.os.call_sync("GetDeploymentBootConfig", GLib.Variant("(sb)", ("", False)),
                                    Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
            return cfg.get("options", "")
        except GLib.Error:
            return ""

    def set_kernel_args(self, added, removed, on_address, on_error):
        existing = self.kernel_args_string()
        self._start("KernelArgs", GLib.Variant("(sasasasa{sv})", (existing, added, [], removed,
                    _asv({"initiating-command-line": "Sloth Center: kernel parameters"}))),
                    "(s)", on_address, on_error)

    def layered_packages(self):
        d = self.default() or self.booted()
        return sorted(set(d.get("requested-packages", []) or []))

    def pkg_change(self, added, removed, on_address, on_error):
        self._start("PkgChange", GLib.Variant("(a{sv}asas)", (_asv({"reboot": False}), added, removed)),
                    "(s)", on_address, on_error)
