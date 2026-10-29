"""Reading the registry of a Windows environment (Wine's text .reg files: system.reg, user.reg).

This tells us after installing what got installed: Windows registers the installed programs under the "Uninstall"
keys (name, publisher, version, install location, icon: this is mostly the program itself).

The format:
  [Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\Battle.net] 1729000000
  "DisplayName"="Battle.net"
  "DisplayIcon"="C:\\\\Program Files (x86)\\\\Battle.net\\\\Battle.net.exe"
  "EstimatedSize"=dword:00012345
"""
import re
from pathlib import Path

UNINSTALL_KEYS = (
    "software\\microsoft\\windows\\currentversion\\uninstall\\",
    "software\\wow6432node\\microsoft\\windows\\currentversion\\uninstall\\",
)
_KEY = re.compile(r"^\[(.+?)\](?:\s+\d+)?\s*$")
_VALUE = re.compile(r'^(@|"(?:[^"\\]|\\.)*")=(.*)$')
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t", "0": "\0"}


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "x":
                m = re.match(r"[0-9a-fA-F]{1,4}", s[i + 2:])
                if m:
                    out.append(chr(int(m.group(0), 16)))
                    i += 2 + len(m.group(0))
                    continue
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _value(raw):
    """A value: text, a number (dword) or None (binary and others, we do not need those)."""
    raw = raw.strip()
    m = re.match(r'^(?:str\(\d\):)?"(.*)"$', raw)
    if m:
        return _unescape(m.group(1))
    if raw.startswith("dword:"):
        try:
            return int(raw[6:], 16)
        except ValueError:
            return None
    return None


def read(path):
    """{key (lowercase, with \\ separators): {value name (lowercase): value}}"""
    keys = {}
    current = None
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return keys
    pending = ""
    for line in lines:
        if pending:
            line = pending + line.lstrip()
            pending = ""
        if line.endswith("\\") and not line.endswith("\\\\"):
            # continuation of a multi-line (hex) value
            pending = line[:-1]
            continue
        m = _KEY.match(line)
        if m:
            current = keys.setdefault(_unescape(m.group(1)).lower(), {})
            continue
        if current is None:
            continue
        m = _VALUE.match(line)
        if m:
            name = "" if m.group(1) == "@" else _unescape(m.group(1)[1:-1])
            value = _value(m.group(2))
            if value is not None:
                current[name.lower()] = value
    return keys


def uninstall_entries(prefix):
    """The programs installed into the Windows environment: {key name: {displayname, displayicon, …}}."""
    out = {}
    for reg in ("system.reg", "user.reg"):
        for key, values in read(Path(prefix) / reg).items():
            for base in UNINSTALL_KEYS:
                if key.startswith(base):
                    name = key[len(base):]
                    if name and "\\" not in name:
                        out.setdefault(name, {}).update(values)
    return out


def exe_from_icon(value):
    """The .exe's Windows path from the DisplayIcon value: '"C:\\X\\a.exe",0' -> 'C:\\X\\a.exe' (if it is an .exe)."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    m = re.match(r'^"([^"]+)"', s)
    s = m.group(1) if m else re.sub(r",\s*-?\d+$", "", s).strip()
    return s if s.lower().endswith(".exe") else None


# Web and system schemes: Wine and the browser handle these, a program never takes them over
COMMON_SCHEMES = {"http", "https", "ftp", "file", "mailto", "news", "nntp", "snews", "telnet", "irc", "ldap",
                  "callto", "tel", "sms", "data", "javascript", "about", "res", "mk", "its", "ms-its"}
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]{1,40}$")


def url_protocols(prefix):
    """The link types (URL schemes) the programs in the environment registered: {scheme: Windows command}.

    A program's login often goes through the browser, which hands the result back with such a link
    (roblox-studio-auth:…, battlenet:…). Windows keeps them under Classes (HKLM in system.reg, HKCU in user.reg):
      [Software\\Classes\\roblox-studio-auth]  "URL Protocol"=""
      [Software\\Classes\\roblox-studio-auth\\shell\\open\\command]  @="\\"C:\\…\\RobloxStudioBeta.exe\\" %1"
    The user's own registration (user.reg) wins, as on Windows.
    """
    base = "software\classes\\"
    out = {}
    for reg in ("system.reg", "user.reg"):
        keys = read(Path(prefix) / reg)
        for key, values in keys.items():
            if not key.startswith(base) or "url protocol" not in values:
                continue
            scheme = key[len(base):]
            if not _SCHEME.match(scheme) or scheme in COMMON_SCHEMES or scheme.startswith("ms-"):
                continue
            command = keys.get(f"{key}\shell\open\command", {}).get("")
            if isinstance(command, str) and command.strip():
                out[scheme] = command.strip()
    return out


def split_command(command, url):
    """A registered command with the link put in: '"C:\X\a.exe" --x "%1"' -> ('C:\X\a.exe', ['--x', url])."""
    # a quoted part is one argument; quotes inside a word (-url:"%1") only group, Windows drops them
    parts = [bare.replace('"', "") if bare else quoted
             for quoted, bare in re.findall(r'"([^"]*)"|((?:[^\s"]|"[^"]*")+)', command)]
    if not parts:
        return None, []
    args = []
    for arg in parts[1:]:
        if re.fullmatch(r"%[1lL]", arg):
            args.append(url)
        elif arg != "%*":
            args.append(arg.replace("%1", url))
    if not any(url in a for a in args):
        args.append(url)
    return parts[0], args
