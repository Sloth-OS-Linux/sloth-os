"""Saved passwords on an automatic sign-in: say when and why the password store asks for the password.

KDE's password store (KWallet) keeps the saved passwords of Wi-Fi networks, network folders and browsers, locked
with the account's password. A normal sign-in unlocks it with the typed password; an automatic sign-in types none,
so it stays locked (unless the disk is encrypted: then the password typed at boot unlocks it, see
files/scripts/kwallet-autologin.sh). The first program that needs a saved password then gets KDE's own "enter the
password for the wallet" window, which says nothing about why (GitHub issue #17: "every network password asks for
the wallet's password").

So at an automatic sign-in (sloth-wallet-notify.service), when the store exists and is still locked a little after
the desktop came up, a notification says it beforehand: why it is locked, that the password is asked once and it
then stays open until the next restart. "Unlock now" asks right away (KDE's window), "Don't remind me" stops the
notification for this account. A password sign-in, a guest (no store), an account without saved passwords and an
encrypted disk's automatic sign-in hear nothing.
Start: python3 -m sloth_center.wallet_notify
"""
import getpass
import json
import os
import subprocess
import time
from pathlib import Path

from .i18n import tr

POLICY = "/etc/sloth-os/admin-policy.json"
QUIET = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "wallet-notify-off"
SETTLE = int(os.environ.get("SLOTH_WALLET_SETTLE", "30"))  # seconds: the boot password's unlock comes first
BUS = ("org.kde.kwalletd6", "/modules/kwalletd6", "org.kde.KWallet")


def autologin_user():
    """The account that signs in automatically (Sloth Center → Accounts), or ""."""
    try:
        users = json.load(open(POLICY, encoding="utf-8")).get("users", {})
    except (OSError, ValueError, AttributeError):
        return ""
    return next((u for u, cfg in users.items() if isinstance(cfg, dict) and cfg.get("autologin")), "")


def wallet_call(method, signature="", *args, timeout=10):
    """Calls the password store over D-Bus -> busctl's answer ("b true", "s \"kdewallet\""), or None."""
    cmd = ["busctl", "--user", f"--timeout={timeout}", "call", *BUS, method]
    if signature:
        cmd += [signature, *map(str, args)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def locked_wallet():
    """The name of the default wallet if it exists and is locked, else "" (also when the store is off or gone)."""
    if wallet_call("isEnabled") != "b true":
        return ""
    answer = wallet_call("localWallet") or ""
    if not answer.startswith("s "):
        return ""
    name = json.loads(answer[2:])
    wallets = wallet_call("wallets") or ""
    if f'"{name}"' not in wallets:
        return ""        # no store yet: nothing saved, nothing to ask
    return name if wallet_call("isOpen", "s", name) == "b false" else ""


def main():
    if getpass.getuser() != autologin_user() or QUIET.exists():
        return 0
    time.sleep(SETTLE)
    wallet = locked_wallet()
    if not wallet:
        return 0
    try:
        answer = subprocess.run(
            ["notify-send", "--app-name=Sloth OS", "--icon=kwalletmanager", "--expire-time=0",
             "--action=unlock=" + tr("Unlock now"), "--action=quiet=" + tr("Don't remind me"),
             tr("Your saved passwords are locked"),
             tr("You signed in automatically, without a password, so your saved passwords (Wi-Fi, network folders, "
                "browsers) could not be unlocked. The first time one is needed, you're asked for your account "
                "password once; after that they stay unlocked until you restart.")],
            capture_output=True, text=True).stdout.strip()
    except OSError:
        return 0
    if answer == "unlock":
        # KDE's own password window; the store stays open after this (Leave Open, /etc/xdg/kwalletrc)
        wallet_call("open", "sxs", wallet, 0, "Sloth OS", timeout=600)
    elif answer == "quiet":
        QUIET.parent.mkdir(parents=True, exist_ok=True)
        QUIET.write_text("1\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
