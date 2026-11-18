"""The computer's information for a feedback (Feedback page): what helps find a problem, with personal details hidden,
shown to the user before it is sent (feedback.py sends exactly the text shown).

collect(): the system's summary and the journal (health.write_log, the same as "Save log"), plus what the developers
had to ask for by hand so far: the computer (processor, memory, graphics), the errors of this start, and the end of
the previous start (a freeze or a hard reset: the TV mode's sleep on the HP, 2026-11-18, was found from there).

redact(): the personal details out, each replaced with a placeholder that says what was there:
  <user>      the accounts' user names (also in home folders' paths), <name> their full names,
  <computer>  the computer's own name (unless it is a name every Sloth OS has, e.g. "sloth"),
  <network>   the saved network connections' (Wi-Fi) names, <mac> hardware addresses, <ip> IP addresses (not
              127.0.0.1 and the like), <email> e-mail addresses, <serial> serial numbers and the machine's ids.
The files' names and contents in the journal are not looked for: the journal does not list the user's files.
"""
import ipaddress
import os
import pwd
import re
import socket
import subprocess
import tempfile
from pathlib import Path

from . import health

LINES = 3000
# host names that say nothing about the person (Sloth OS's own, the installers' defaults)
COMMON_HOSTS = {"sloth", "sloth-os", "slothos", "localhost", "fedora", "localhost-live", "linux"}
# connection names NetworkManager makes up itself: not the person's
COMMON_NETWORKS = {"lo", "virbr0", "docker0", "podman0"}

EXTRA = [
    ("Computer", ["sh", "-c", "uname -r; lscpu | grep -E '^(Model name|CPU\\(s\\)):'; "
                              "grep -E '^(MemTotal|SwapTotal):' /proc/meminfo; lspci -nn | grep -Ei 'vga|3d|display'"]),
    ("Errors of this start", ["journalctl", "--no-pager", "-b", "-p", "3", "-n", "200"]),
    ("The end of the previous start", ["journalctl", "--no-pager", "-b", "-1", "-n", "150"]),
]


def collect(lines=LINES):
    """The raw information (not redacted yet). -> text"""
    fd, path = tempfile.mkstemp(prefix="sloth-diagnostics-", suffix=".txt")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            for title, cmd in EXTRA:
                f.write(f"===== {title}\n")
                f.flush()
                try:
                    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=30)
                except (OSError, subprocess.SubprocessError) as e:
                    f.write(f"({e})\n")
                f.write("\n")
        rest = path + ".log"
        try:
            health.write_log(rest, lines=lines)
            text = Path(path).read_text(encoding="utf-8", errors="replace") + \
                Path(rest).read_text(encoding="utf-8", errors="replace")
        finally:
            if os.path.exists(rest):
                os.unlink(rest)
    finally:
        os.unlink(path)
    return text


# --- What is personal ---------------------------------------------------------------------------------------

def personal():
    """The personal words of this computer: {"users": [...], "names": [...], "host": str, "networks": [...],
    "ids": [...]}"""
    users, names = set(), set()
    for p in pwd.getpwall():
        if 1000 <= p.pw_uid < 60000:
            users.add(p.pw_name)
            full = (p.pw_gecos or "").split(",")[0].strip()
            if full and full != p.pw_name:
                names.add(full)
    try:
        users.add(pwd.getpwuid(os.getuid()).pw_name)
    except KeyError:
        pass
    host = socket.gethostname().split(".")[0]
    networks = []
    try:
        out = subprocess.run(["nmcli", "-t", "-f", "NAME", "connection", "show"], capture_output=True, text=True,
                             timeout=10).stdout
        networks = [n.replace("\\:", ":") for n in out.splitlines() if n and n not in COMMON_NETWORKS]
    except (OSError, subprocess.SubprocessError):
        pass
    ids = []
    for f in ("/etc/machine-id", "/proc/sys/kernel/random/boot_id"):
        try:
            value = Path(f).read_text().strip()
        except OSError:
            continue
        if value:
            ids += [value, value.replace("-", "")]
    return {"users": sorted(users), "names": sorted(names), "host": host, "networks": networks, "ids": ids}


_MAC = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])")
# not a version with four numbers (a kernel's 6.6.87.2-microsoft…: a dash or a letter follows)
_IPV4 = re.compile(r"(?<![\d.\w-])(?:\d{1,3}\.){3}\d{1,3}(?![\d.]|-\w|[A-Za-z])")
# an IPv6 address: with "::", or with at least five groups (so that a time, 10:10:44, never counts)
_IPV6 = re.compile(r"(?<![\w:.])(?:(?:[0-9A-Fa-f]{1,4}:){5,7}[0-9A-Fa-f]{1,4}"
                   r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,5})?"
                   r"|::(?:[0-9A-Fa-f]{1,4}:){0,5}[0-9A-Fa-f]{1,4})(?:/\d{1,3})?(?![\w:])")
_EMAIL = re.compile(r"[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# systemd's units with an instance (user@1000.service, app-x@autostart.service) are not e-mail addresses
_UNITS = (".service", ".socket", ".target", ".timer", ".mount", ".scope", ".slice", ".path", ".device", ".swap",
          ".automount")
_SERIAL = re.compile(r"(?im)^(\s*(?:[\w.]*serial[\w.]*|wwn|id_wwn\w*)\s*[:=]\s*)(\S.*)$")


def _ip4(m):
    try:
        ip = ipaddress.ip_address(m.group(0))
    except ValueError:
        return m.group(0)        # not an address (e.g. 999.1.2.3)
    if ip.is_loopback or ip.is_unspecified or str(ip).startswith("255."):
        return m.group(0)
    return "<ip>"


def _ip6(m):
    text = m.group(0)
    address = text.split("/")[0]
    # a C++ name (Bad::Add, PLASMALOGIN::Session) can look like one: an address has a digit, and its letters are all
    # small or all capital
    if not any(c.isdigit() for c in address) or (address.lower() != address and address.upper() != address):
        return text
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return text
    return text if ip.is_loopback or ip.is_unspecified else "<ip>"


def _word(value):
    """A whole-word pattern: not a part of a longer name (sloth-tv-session stays when the user is "sloth")."""
    return re.compile(r"(?<![\w-])" + re.escape(value) + r"(?![\w-])")


def redact(text, facts=None):
    """The personal details out of a text (see the module's description). -> text"""
    facts = personal() if facts is None else facts
    text = _SERIAL.sub(lambda m: m.group(1) + "<serial>", text)
    for value in facts.get("ids", []):
        text = text.replace(value, "<serial>")
    text = _EMAIL.sub(lambda m: m.group(0) if m.group(0).endswith(_UNITS) else "<email>", text)
    text = _MAC.sub("<mac>", text)
    text = _IPV6.sub(_ip6, text)
    text = _IPV4.sub(_ip4, text)
    # longer values first, so that a full name goes before a user name it contains
    for value in sorted(facts.get("networks", []), key=len, reverse=True):
        if len(value) >= 3:
            text = _word(value).sub("<network>", text)
    for value in sorted(facts.get("names", []), key=len, reverse=True):
        if len(value) >= 3:
            text = _word(value).sub("<name>", text)
    host = facts.get("host", "")
    if host and host.lower() not in COMMON_HOSTS and host not in facts.get("users", []):
        text = _word(host).sub("<computer>", text)
    for value in sorted(facts.get("users", []), key=len, reverse=True):
        if len(value) >= 2:
            text = _word(value).sub("<user>", text)
    return text


def bundle(lines=LINES):
    """What a feedback sends: collected, then redacted. -> text"""
    return redact(collect(lines))
