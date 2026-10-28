"""When the automatic system update runs.

rpm-ostreed-automatic.timer downloads and prepares the system update (AutomaticUpdatePolicy=stage). From the base
image it runs an hour after start, a day after its last run and daily at 4:00 (Universal Blue's override.conf), and
never on a metered connection (the service's ExecCondition). Sloth Center → Updates sets one time of day instead,
through sloth-helper update-time, which writes a drop-in (UPDATE_TIME_CONF) that clears the other triggers;
Persistent=true makes a missed run happen at the next start. This module only reads (no root needed).
App updates (flatpak-system-update.timer) are not changed: they run soon after start, and they are small.
"""
import glob
import os
import re

UPDATE_TIMER = "/usr/lib/systemd/system/rpm-ostreed-automatic.timer"
# Our drop-in; without it the base image's times are used
UPDATE_TIME_CONF = "/etc/systemd/system/rpm-ostreed-automatic.timer.d/zz-sloth-time.conf"
DEFAULT_HOUR = 4
_HOUR = re.compile(r"^OnCalendar=\S*\s(\d{1,2}):\d{2}", re.M)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def update_hour(timer=UPDATE_TIMER, conf=UPDATE_TIME_CONF):
    """The hour the automatic update runs: ours if set, otherwise the base image's (its drop-ins too, the last
    OnCalendar wins as in systemd); -1 if there is no timer."""
    base = _read(timer)
    if base is None:
        return -1
    vendor = [_read(p) or "" for p in sorted(glob.glob(os.path.join(timer + ".d", "*.conf")))]
    for text in [_read(conf) or "", *reversed(vendor), base]:
        hours = _HOUR.findall(text)
        if hours:
            return int(hours[-1])
    return DEFAULT_HOUR
