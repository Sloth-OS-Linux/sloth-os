"""A Windows-környezet registryjének olvasása (a Wine szöveges .reg fájljai: system.reg, user.reg).

Ebből tudjuk meg telepítés után, mi települt: a Windows a telepített programokat az „Uninstall”
kulcsok alá jegyzi be (név, kiadó, verzió, telepítési hely, ikon: ez többnyire maga a program).

A formátum:
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
    """Egy érték: szöveg, szám (dword) vagy None (bináris és egyéb, ezekre nincs szükségünk)."""
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
    """{kulcs (kisbetűs, \\ elválasztóval): {érték neve (kisbetűs): érték}}"""
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
            # többsoros (hex) érték folytatása
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
    """A Windows-környezetbe telepített programok: {kulcs neve: {displayname, displayicon, …}}."""
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
    """A DisplayIcon értékéből a .exe Windows-útja: '"C:\\X\\a.exe",0' -> 'C:\\X\\a.exe' (ha .exe)."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    m = re.match(r'^"([^"]+)"', s)
    s = m.group(1) if m else re.sub(r",\s*-?\d+$", "", s).strip()
    return s if s.lower().endswith(".exe") else None
