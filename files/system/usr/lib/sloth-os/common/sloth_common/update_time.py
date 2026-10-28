"""When the automatic update runs: uupd.timer (Universal Blue) runs daily at 4:00, or at the next start if the
computer was off then. Sloth Center → Updates changes the hour through sloth-helper update-time, which writes a
drop-in (UPDATE_TIME_CONF); this module only reads it (no root needed).
"""
import re

UPDATE_TIMER = "/usr/lib/systemd/system/uupd.timer"
# Our drop-in; without it the base image's time is used
UPDATE_TIME_CONF = "/etc/systemd/system/uupd.timer.d/50-sloth-time.conf"
DEFAULT_HOUR = 4
_HOUR = re.compile(r"^OnCalendar=\S*\s(\d{1,2}):\d{2}", re.M)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def update_hour(timer=UPDATE_TIMER, conf=UPDATE_TIME_CONF):
    """The hour the automatic update runs: ours if set, otherwise the base image's; -1 if there is no timer."""
    base = _read(timer)
    if base is None:
        return -1
    for text in (_read(conf) or "", base):
        hours = _HOUR.findall(text)
        if hours:
            return int(hours[-1])
    return DEFAULT_HOUR
