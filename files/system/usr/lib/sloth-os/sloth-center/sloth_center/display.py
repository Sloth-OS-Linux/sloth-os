"""Displays for gaming (Drivers and hardware page): the refresh rate, variable refresh rate (FreeSync, G-Sync) and HDR.

Many monitors run below what they can (a 144 Hz monitor at 60 or 100 Hz) because nobody switched them. This shows
each connected monitor by its own name (from the EDID, not "DP-4"), its refresh rate now and the highest one at the
same resolution, with a button for it, and switches for VRR and HDR where the monitor supports them. Everything goes
through KDE's kscreen-doctor (as the user, no password). After a change the page asks whether to keep it, and goes
back by itself (revert) if nobody answers, as KDE's own display settings do: a black screen cannot get stuck.
"""
import json
import logging
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from .i18n import tr

log = logging.getLogger("sloth-center.display")

DRM = Path("/sys/class/drm")


def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("%s: %s", cmd[0], e)
        return ""


def edid_name(edid):
    """The monitor's own name from its EDID (the 0xFC display descriptor), or ""."""
    if len(edid) < 128:
        return ""
    for offset in (54, 72, 90, 108):
        block = edid[offset:offset + 18]
        if block[0:3] == b"\0\0\0" and block[3] == 0xFC:
            return block[5:18].split(b"\n")[0].decode("cp437", "replace").strip()
    return ""


def _monitor_name(connector):
    for path in DRM.glob(f"card*-{connector}/edid"):
        try:
            name = edid_name(path.read_bytes())
        except OSError:
            continue
        if name:
            return name
    return connector


def _vrr(text):
    """{connector: "incapable" | "automatic" | "always" | "never"} from `kscreen-doctor -o` (VRR is not in -j)."""
    result, current = {}, None
    for line in re.sub(r"\x1b\[[0-9;]*m", "", text).splitlines():
        m = re.match(r"Output:\s+\d+\s+(\S+)", line.strip())
        if m:
            current = m.group(1)
        elif current and line.strip().lower().startswith("vrr:"):
            result[current] = line.split(":", 1)[1].strip().lower()
    return result


def outputs(run=_run, name_of=_monitor_name):
    """The connected, turned-on monitors: [{connector, name, size, hz, bestHz, bestMode, previousMode, vrr, hdr}].
    vrr / hdr: "" if the monitor cannot do it, otherwise "on" or "off"."""
    try:
        data = json.loads(run(["kscreen-doctor", "-j"]) or "{}")
    except ValueError:
        return []
    vrr = _vrr(run(["kscreen-doctor", "-o"]))
    result = []
    for o in data.get("outputs", []):
        if not (o.get("connected") and o.get("enabled")):
            continue
        modes = {str(m.get("id")): m for m in o.get("modes", [])}
        current = modes.get(str(o.get("currentModeId")))
        if not current:
            continue
        size = current.get("size") or {}
        same_size = [m for m in modes.values() if m.get("size") == size]
        best = max(same_size, key=lambda m: m.get("refreshRate", 0))
        policy = vrr.get(o.get("name", ""), "incapable")
        result.append({
            "connector": o.get("name", ""),
            "name": name_of(o.get("name", "")),
            "size": f"{size.get('width', 0)}×{size.get('height', 0)}",
            "hz": round(current.get("refreshRate", 0)),
            "bestHz": round(best.get("refreshRate", 0)),
            # by id: two modes can share a name (e.g. two "1920x1080@60"); kscreen-doctor takes either
            "bestMode": str(best.get("id", "")),
            "previousMode": str(current.get("id", "")),
            # the "hdr" key is only there when the monitor can do HDR
            "hdr": ("on" if o["hdr"] else "off") if "hdr" in o else "",
            "vrr": "" if policy == "incapable" else ("off" if policy == "never" else "on"),
        })
    return result


class DisplayController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._outputs = []
        self._undo = []       # the kscreen-doctor arguments that put back the previous setting
        self._undo_extra = None   # and what else goes back with it (a profile's sound devices)
        self._error = ""
        # the monitors are read when the Drivers and hardware page opens (not at every start of Sloth Center)

    monitors = Property("QVariantList", lambda self: list(self._outputs), notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    confirming = Property(bool, lambda self: bool(self._undo), notify=changed)

    @Slot()
    def refresh(self):
        self._outputs = outputs()
        self.changed.emit()

    def _apply(self, args, undo, undo_extra=None):
        """Applies, then the page asks "Keep this setting?" (revert puts back `undo`, and runs `undo_extra`)."""
        self._error = ""
        r = subprocess.run(["kscreen-doctor", *args], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            log.warning("kscreen-doctor %s: %s", args, r.stderr.strip())
            self._error = tr("Couldn't change the display.")
            self._undo, self._undo_extra = [], None
            if undo_extra:
                undo_extra()
        else:
            self._undo, self._undo_extra = undo, undo_extra
        self.refresh()

    def screens(self):
        """kscreen-doctor -j's data now (for the profiles)."""
        try:
            return json.loads(_run(["kscreen-doctor", "-j"]) or "{}")
        except ValueError:
            return {}

    @Slot(str)
    def useBestRefresh(self, connector):
        o = next((o for o in self._outputs if o["connector"] == connector), None)
        if o and o["bestMode"]:
            self._apply([f"output.{connector}.mode.{o['bestMode']}"],
                        [f"output.{connector}.mode.{o['previousMode']}"])

    @Slot(str, bool)
    def setVrr(self, connector, on):
        self._apply([f"output.{connector}.vrrpolicy.{'automatic' if on else 'never'}"],
                    [f"output.{connector}.vrrpolicy.{'never' if on else 'automatic'}"])

    @Slot(str, bool)
    def setHdr(self, connector, on):
        # HDR goes together with the wide color gamut, as in KDE's display settings
        state, back = ("enable", "disable") if on else ("disable", "enable")
        self._apply([f"output.{connector}.hdr.{state}", f"output.{connector}.wcg.{state}"],
                    [f"output.{connector}.hdr.{back}", f"output.{connector}.wcg.{back}"])

    @Slot()
    def keep(self):
        self._undo, self._undo_extra = [], None
        self.changed.emit()

    @Slot()
    def revert(self):
        undo, extra, self._undo, self._undo_extra = self._undo, self._undo_extra, [], None
        if undo:
            subprocess.run(["kscreen-doctor", *undo], capture_output=True, timeout=20)
        if extra:
            extra()
        self.refresh()

    @Slot()
    def openSettings(self):
        try:
            subprocess.Popen(["systemsettings", "kcm_kscreen"], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            log.warning("System Settings: %s", e)
