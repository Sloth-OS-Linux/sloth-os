"""The sign-in PIN's state for your own account, asked from its keeper (/usr/libexec/sloth-os/pin-verifier, behind
/run/sloth-os/pin.sock; its files are root's). Light on purpose: Sloth Center's Account and security page and the
sign-in notification (pin_notify) both use it."""
import json
from pathlib import Path

PIN_SOCKET = "/run/sloth-os/pin.sock"   # the PIN's keeper (/usr/libexec/sloth-os/pin-verifier): its files are root's


def pin_status(user):
    """{"set", "tpm", "wallet"} for your own account: the PIN's keeper answers (its files are root-only).
    wallet: the PIN also opens the password store (KWallet) at sign-in (it was set together with the password);
    dropped: it did, until the account password changed (the kept copy was dropped)."""
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(10)
            conn.connect(PIN_SOCKET)
            conn.sendall(json.dumps({"user": user, "status": True}).encode() + b"\n")
            data = json.loads(conn.recv(256).decode() or "{}")
            return {"set": bool(data.get("set")), "tpm": bool(data.get("tpm")), "wallet": bool(data.get("wallet")),
                    "dropped": bool(data.get("dropped"))}
    except (OSError, ValueError):
        return {"set": False, "tpm": False, "wallet": False, "dropped": False}


def has_tpm():
    """A security chip the PIN (and with it the password for the password store) can be kept in."""
    return Path("/dev/tpmrm0").exists()
