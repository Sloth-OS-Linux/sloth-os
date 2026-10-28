"""The download speed limit (Sloth Center → System status): how fast the whole computer downloads, so the rest of
the home network stays fast (a call, a game, another computer).

Neither rpm-ostree nor Flatpak can limit their own download, so the limit is on the network connection: tc's
ingress policer on the interfaces with a default route: every download of the computer. It applies always (the
default), or only while the system or app updates run (rpm-ostreed.service, flatpak-system-update.service:
their drop-ins call net-limit update-start / update-stop). A connection that comes up later gets it from the
NetworkManager dispatcher (net-limit apply). The setting: /etc/sloth-os/net-limit.json ({"kbit": the limit in
kbit/s, "unit": the unit the user chose, "when"}), written by sloth-helper net-limit, without a password
(org.slothos.helper.netlimit: it only slows the computer down, it cannot harm anything). This module holds the
logic; /usr/libexec/sloth-os/net-limit runs the commands.
"""
import json

CONFIG = "/etc/sloth-os/net-limit.json"
# kbit/s in one unit (decimal, as networks count): KB/s is 8 kbit/s, MB/s is 8000 kbit/s
UNITS = {"kbit": 1, "KB": 8, "Mbit": 1000, "MB": 8000}
WHEN = ("always", "updates")
MIN_KBIT = 64            # below this a connection hardly works at all
MAX_KBIT = 10_000_000    # 10 Gbit/s
UPDATE_UNITS = ("rpm-ostreed.service", "flatpak-system-update.service")


def to_kbit(value, unit):
    """A number in a unit -> kbit/s, or 0 if it is not a usable limit."""
    if unit not in UNITS or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return 0
    kbit = round(value * UNITS[unit])
    return kbit if MIN_KBIT <= kbit <= MAX_KBIT else 0


def load(path=CONFIG):
    """{"kbit": the limit (0: none), "unit", "value": the limit in that unit, "when"}; anything wrong means no limit."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    kbit = data.get("kbit")
    if isinstance(kbit, bool) or not isinstance(kbit, int) or not MIN_KBIT <= kbit <= MAX_KBIT:
        kbit = 0
    unit = data.get("unit") if data.get("unit") in UNITS else "MB"
    when = data.get("when") if data.get("when") in WHEN else "always"
    value = kbit / UNITS[unit]
    return {"kbit": kbit, "unit": unit, "value": int(value) if value == int(value) else round(value, 2), "when": when}


def wanted(cfg, op, active_units, stopping=""):
    """Whether the limit should be on now. op: "apply" (a connection came up, the setting changed),
    "update-start" or "update-stop" (an update service starts / stops; stopping: its name)."""
    if cfg["kbit"] <= 0:
        return False
    if cfg["when"] == "always" or op == "update-start":
        return True
    return any(u != stopping for u in active_units)


def default_devices(*route_lists):
    """The interfaces with a default route, from `ip -j route show default` (IPv4 and IPv6)."""
    devs = set()
    for routes in route_lists:
        for r in routes or []:
            if isinstance(r, dict) and r.get("dev") and r.get("dev") != "lo":
                devs.add(r["dev"])
    return sorted(devs)


def police(kbit):
    """tc police arguments: the rate, and a burst of 0.2 s at that rate (at least 16 000 bytes)."""
    return ["rate", f"{kbit}kbit", "burst", str(max(16000, kbit * 1000 // 8 // 5))]


def on_commands(dev, kbit):
    return [["tc", "qdisc", "add", "dev", dev, "handle", "ffff:", "ingress"],
            ["tc", "filter", "add", "dev", dev, "parent", "ffff:", "protocol", "all", "matchall",
             "action", "police", *police(kbit), "drop"]]


def off_command(dev):
    return ["tc", "qdisc", "del", "dev", dev, "ingress"]
