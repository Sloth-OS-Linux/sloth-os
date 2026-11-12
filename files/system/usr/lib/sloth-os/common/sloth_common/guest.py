"""The guest account (Sloth Center → Account and security): which account it is, for the tools that treat it apart.

sloth-helper-family's guest-on makes it and writes /etc/sloth-os/guest.json ({"user": name, "uid": number});
guest-off removes both. The guest signs in without a password, is never an administrator, and everything it leaves
behind is deleted when it signs out and at every start (/usr/libexec/sloth-os/guest-reset). Sloth Welcome does not
open for it (its home starts empty every time), and parental controls do not list it as a child.
"""
import json
from pathlib import Path

MARKER = Path("/etc/sloth-os/guest.json")


def guest():
    """{"user": name, "uid": number} of the guest account, or None when there is none."""
    try:
        data = json.loads(MARKER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("user"), str) and isinstance(data.get("uid"), int):
        return data
    return None


def is_guest(name):
    g = guest()
    return bool(g) and g["user"] == name
