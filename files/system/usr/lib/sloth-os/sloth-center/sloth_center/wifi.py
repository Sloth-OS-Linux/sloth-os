"""Wi-Fi check (System status → Network): step by step, in plain language, with a button where one helps.

The steps: is there a Wi-Fi adapter, is it turned on (a key or switch on the computer, or only in software), is it
connected to a network, how strong the signal is, does the internet answer (or does the network want a sign-in
first, as in hotels and on trains). It stops at the first step that is not right, since the later ones depend on
it. Everything is read from NetworkManager (nmcli) and rfkill; nothing is scanned or changed by the check itself.
"""
import logging
import re
import subprocess

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from .i18n import N_, tr

log = logging.getLogger("sloth-center.wifi")

OK, WARN, ERROR = "ok", "warning", "error"
WEAK_SIGNAL = 40  # percent, as NetworkManager shows it
# An address that a sign-in network (hotel, train) redirects to its sign-in page: the one Fedora's own check uses
PORTAL_URL = "http://fedoraproject.org/static/hotspot.txt"

TITLES = {
    "adapter": N_("Wi-Fi adapter"),
    "switch": N_("Wi-Fi switch"),
    "network": N_("Wi-Fi network"),
    "signal": N_("Signal"),
    "internet": N_("Internet"),
}


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return None


def _fields(line):
    """nmcli -t fields: separated by ":", a ":" inside a value (e.g. in a network name) is written as "\\:"."""
    return [f.replace("\\:", ":").replace("\\\\", "\\") for f in re.split(r"(?<!\\):", line)]


def _step(step_id, state, text, action=""):
    return {"id": step_id, "state": state, "text": text, "action": action}


def diagnose(run=_run):
    """The steps checked so far: [{id, state, text, action}]; the last one is the problem (if any)."""
    steps = []
    devices = [_fields(l) for l in (run(["nmcli", "-t", "-f", "TYPE,STATE,DEVICE", "device"]) or "").splitlines()]
    wifi = [d for d in devices if len(d) >= 3 and d[0] == "wifi"]
    if not wifi:
        steps.append(_step("adapter", ERROR, tr("No Wi-Fi adapter was found. If this computer has Wi-Fi, it may need a driver: Drivers and hardware can help. A USB Wi-Fi adapter also works."), "drivers"))
        return steps
    steps.append(_step("adapter", OK, tr("This computer has a Wi-Fi adapter.")))

    hard = soft = False
    for line in (run(["rfkill", "-n", "-o", "TYPE,SOFT,HARD"]) or "").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "wlan":
            soft = soft or parts[1] == "blocked"
            hard = hard or parts[2] == "blocked"
    if hard:
        steps.append(_step("switch", ERROR, tr("Wi-Fi is turned off with a key or switch on the computer. Turn it on with it: often Fn together with a key showing an antenna or an airplane.")))
        return steps
    if soft or (run(["nmcli", "-t", "radio", "wifi"]) or "").strip() == "disabled":
        steps.append(_step("switch", WARN, tr("Wi-Fi is turned off."), "turnOn"))
        return steps
    steps.append(_step("switch", OK, tr("Wi-Fi is turned on.")))

    states = [d[1] for d in wifi]
    if not any(s.startswith("connected") for s in states):
        if all(s == "unavailable" for s in states):
            steps.append(_step("network", ERROR, tr("The Wi-Fi adapter is there but not ready. Restarting the computer often helps; if not, Drivers and hardware can help."), "drivers"))
        elif any(s.startswith("connecting") for s in states):
            steps.append(_step("network", WARN, tr("Connecting to a Wi-Fi network… If this takes long, check the password, or choose the network again."), "networks"))
        else:
            steps.append(_step("network", WARN, tr("Not connected to a Wi-Fi network. Choose yours from the list and enter its password."), "networks"))
        return steps

    ssid, signal = "", None
    for line in (run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi", "list", "--rescan", "no"]) or "").splitlines():
        parts = _fields(line)
        if len(parts) == 3 and parts[0] == "yes":
            ssid = parts[1]
            signal = int(parts[2]) if parts[2].isdigit() else None
            break
    steps.append(_step("network", OK, tr("Connected to {name}.", name=ssid) if ssid else tr("Connected to a Wi-Fi network.")))
    if signal is not None:
        if signal < WEAK_SIGNAL:
            steps.append(_step("signal", WARN, tr("The signal is weak ({n}%). Move closer to the router, or away from walls and large metal objects.", n=signal)))
        else:
            steps.append(_step("signal", OK, tr("The signal is good ({n}%).", n=signal)))

    connectivity = (run(["nmcli", "-t", "-f", "CONNECTIVITY", "general"]) or "").strip()
    if connectivity == "full":
        steps.append(_step("internet", OK, tr("The internet works.")))
    elif connectivity == "portal":
        steps.append(_step("internet", WARN, tr("This network wants you to sign in first, as in hotels, cafés and on trains."), "portal"))
    elif connectivity in ("limited", "none"):
        steps.append(_step("internet", ERROR, tr("Connected to the router, but the internet does not answer. Restart the router (unplug it for 10 seconds), or ask whoever runs the network.")))
    return steps


class WifiController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._steps = []
        self._busy = False

    busy = Property(bool, lambda self: self._busy, notify=changed)

    @Property("QVariantList", notify=changed)
    def steps(self):
        return [{**s, "title": tr(TITLES[s["id"]])} for s in self._steps]

    @Slot()
    def check(self):
        self._busy = True
        self.changed.emit()
        # first show "Checking…", then look (it takes a moment)
        QTimer.singleShot(50, self._check)

    def _check(self):
        try:
            self._steps = diagnose()
        finally:
            self._busy = False
            self.changed.emit()

    @Slot(str)
    def act(self, action):
        if action == "turnOn":
            _run(["nmcli", "radio", "wifi", "on"])
            # the adapter needs a few seconds to find the networks again
            self._busy = True
            self.changed.emit()
            QTimer.singleShot(4000, self._check)
        elif action == "networks":
            self._open(["systemsettings", "kcm_networkmanagement"])
        elif action == "portal":
            self._open(["xdg-open", PORTAL_URL])

    def _open(self, cmd):
        try:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("%s: %s", cmd[0], e)
