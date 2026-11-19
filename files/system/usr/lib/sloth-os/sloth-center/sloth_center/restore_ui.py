"""Sloth Center → Updates → Restore points: the list, "Create a restore point", going back to one, letting one go
(restore_points.py does the work)."""
import datetime
import json
import logging
import subprocess
import threading

from PySide6.QtCore import QObject, Property, Signal, Slot

from . import restore_points as rp
from . import texts
from .i18n import tr

log = logging.getLogger("sloth-center.restore-points")


class RestorePointsController(QObject):
    changed = Signal()
    _loaded = Signal(object)
    _done = Signal(str, bool)          # (text, whether a restart finishes it)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []
        self._busy = False
        self._info = ""
        self._error = ""
        self._restart = False
        self._loaded.connect(self._on_loaded)
        self._done.connect(self._on_done)
        self.refresh()

    points = Property("QVariantList", lambda self: list(self._points), notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    infoText = Property(str, lambda self: self._info, notify=changed)
    errorText = Property(str, lambda self: self._error, notify=changed)
    needsRestart = Property(bool, lambda self: self._restart, notify=changed)

    @Property(str, notify=changed)
    def pendingId(self):
        job = rp.pending()
        return job.get("id", "") if job else ""

    @Slot()
    def refresh(self):
        def work():
            booted, deploys = rp.booted_checksum()
            self._loaded.emit(rp.describe(rp.load(), booted, deploys))
        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, points):
        rows = []
        for p in points:
            when = datetime.datetime.fromtimestamp(p["when"]).astimezone()
            system = {"same": tr("The system version is the same as now"),
                      "earlier": tr("An earlier system version"),
                      "gone": tr("Its system version is no longer on the computer")}[p["system"]]
            rows.append(dict(p, title=tr(rp.REASON_TEXTS.get(p["reason"], rp.REASON_TEXTS["manual"])),
                             dateText=texts.datetime_text(when),
                             detail=system + " · " + (tr("Settings saved") if p["settings"]
                                                      else tr("No saved settings")),
                             canGoBack=p["system"] == "earlier" or p["settings"]))
        self._points = rows
        self.changed.emit()

    def _work(self, fn):
        if self._busy:
            return
        self._busy, self._info, self._error = True, "", ""
        self.changed.emit()

        def run():
            try:
                text, restart = fn()
            except Exception as e:  # noqa: BLE001
                log.warning("restore points: %s", e)
                text, restart = "!" + tr("That didn't work. Please try again."), False
            self._done.emit(text, restart)
        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, text, restart):
        self._busy = False
        if text.startswith("!"):
            self._error = text[1:]
        else:
            self._info, self._restart = text, restart or self._restart
        self.changed.emit()
        self.refresh()

    @Slot()
    def createNow(self):
        def work():
            if rp.create("manual"):
                return tr("Done: a restore point was made."), False
            return "!" + tr("Couldn't make a restore point. Please try again."), False
        self._work(work)

    @Slot(str)
    def remove(self, point_id):
        def work():
            if rp.pending() and rp.pending().get("id") == point_id:
                rp.cancel_settings()
            if rp.delete(point_id):
                return tr("Done: the restore point is deleted."), False
            return "!" + tr("Couldn't delete the restore point."), False
        self._work(work)

    @Slot(str)
    def goBack(self, point_id):
        point = next((p for p in rp.load() if p["id"] == point_id), None)
        row = next((p for p in self._points if p["id"] == point_id), None)
        if point is None or row is None:
            return

        def work():
            if row["system"] == "earlier":
                index = _deployment_index(point.get("checksum", ""))
                if index is None or not _set_default(index):
                    return "!" + tr("That didn't work. This needs administrator approval."), False
            if row["settings"]:
                rp.schedule_settings(point)
            return tr("Done. Restart the computer to finish: it starts as it was at this restore point. Your files "
                      "stay as they are; the settings in use now are kept aside."), True
        self._work(work)


def _deployment_index(checksum):
    try:
        out = subprocess.run(["rpm-ostree", "status", "--json"], capture_output=True, text=True, timeout=60).stdout
        for i, d in enumerate(json.loads(out or "{}").get("deployments", [])):
            if d.get("checksum") == checksum:
                return i
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _set_default(index):
    try:
        r = subprocess.run(["pkexec", rp.HELPER_VERSIONS, "set-default", str(index)], capture_output=True, text=True,
                           timeout=300)
        return bool(json.loads(r.stdout or "{}").get("ok"))
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
