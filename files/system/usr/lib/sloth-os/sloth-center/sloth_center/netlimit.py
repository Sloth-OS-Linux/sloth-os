"""The download speed limit (System status page): how fast the whole computer downloads, so the rest of the home
network stays fast. The logic: sloth_common.net_limit; it is set through sloth-helper-netlimit, without a password
(it can only slow the downloads down), and takes effect at once."""
import json
import logging
import subprocess

from PySide6.QtCore import QObject, Property, Signal, Slot
from sloth_common import net_limit

from .i18n import tr

log = logging.getLogger("sloth-center.netlimit")


class NetLimitController(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._error = ""

    error = Property(str, lambda self: self._error, notify=changed)

    @Property("QVariantMap", notify=changed)
    def state(self):
        """{"on", "value": the limit in "unit", "unit", "when": "always" | "updates", "units": [...]}"""
        cfg = net_limit.load()
        return {"on": cfg["kbit"] > 0, "value": cfg["value"] or 10, "unit": cfg["unit"], "when": cfg["when"],
                "units": list(net_limit.UNITS)}

    @Slot(bool, float, str, str)
    def set(self, on, value, unit, when):
        if unit not in net_limit.UNITS or when not in net_limit.WHEN:
            return
        kbit = net_limit.to_kbit(value, unit)
        if on and not kbit:
            self._error = tr("Choose a limit between 64 kbit/s and 10 000 Mbit/s.")
            self.changed.emit()
            return
        self._error = ""
        try:
            r = subprocess.run(["pkexec", "/usr/libexec/sloth-os/sloth-helper-netlimit", "net-limit",
                                str(kbit) if on else "off", unit, when],
                               capture_output=True, text=True, timeout=60)
            ok = json.loads(r.stdout or "{}").get("ok", False)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            log.warning("net-limit: %s", e)
            ok = False
        if not ok:
            self._error = tr("Couldn't change the limit.")
        self.changed.emit()
