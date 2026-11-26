"""The PIN and the saved passwords: after the update that brought it, say once what to do.

Since 2026-11-26 a PIN set up together with the account password (Sloth Center → Account and security, only with a
TPM) also unlocks the password store (KWallet) at sign-in, like Windows Hello (pin-verifier, pam_sloth_pin.so). A
PIN set up before that update still signs in, but the store then asks for the password at its first use; to change
that, the PIN has to be set once more with the password.

So at the first sign-in after the update (sloth-pin-notify.service runs at every sign-in, but speaks up only once),
an account with a PIN in the TPM that does not unlock the store gets a notification saying what to do. "Set it up
now" opens Sloth Center's Account and security page, where the PIN row says the same until it is done. The same
once more if the account password changes later (pin-verifier then drops the PIN's copy of it). Nothing without a
PIN, without a TPM, or when the PIN already unlocks the store.
Start: python3 -m sloth_center.pin_notify
"""
import getpass
import os
import subprocess
import time
from pathlib import Path

from .pin_state import has_tpm, pin_status
from .i18n import tr

# the reason already told ("old" or "changed"); removed once the PIN unlocks the store, so a later change is told
SAID = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "sloth-os" / "pin-notify-said"
SETTLE = int(os.environ.get("SLOTH_PIN_NOTIFY_SETTLE", "20"))  # seconds: let the desktop come up first


def reason(status, tpm):
    """"old" (a PIN from before, without the password), "changed" (the password changed since), "" (nothing)."""
    if not (tpm and status.get("set") and status.get("tpm")) or status.get("wallet"):
        return ""
    return "changed" if status.get("dropped") else "old"


def where():
    """Where to do it, in the words of Sloth Center itself."""
    return " → ".join(("Sloth Center", tr("Account and security"), tr("Change PIN")))


def message(why):
    if why == "changed":
        return (tr("Your PIN no longer unlocks your saved passwords"),
                tr("Your account password changed. Set your PIN once more and type your new password with it: {path}.",
                   path=where()))
    return (tr("Your PIN can unlock your saved passwords"),
            tr("Sloth OS can now unlock your saved passwords (Wi-Fi, network folders) when you sign in with your PIN. "
               "Set your PIN once more and type your account password with it: {path}.", path=where()))


def main():
    time.sleep(SETTLE)
    status = pin_status(getpass.getuser())
    why = reason(status, has_tpm())
    if not why:
        if status.get("wallet"):
            SAID.unlink(missing_ok=True)      # done: a later password change is told again
        return 0
    try:
        if SAID.read_text().strip() == why:
            return 0                          # told once already
    except OSError:
        pass
    SAID.parent.mkdir(parents=True, exist_ok=True)
    SAID.write_text(why + "\n")
    title, body = message(why)
    try:
        answer = subprocess.run(
            ["notify-send", "--app-name=Sloth OS", "--icon=dialog-password", "--expire-time=0",
             "--action=setup=" + tr("Set it up now"), title, body],
            capture_output=True, text=True).stdout.strip()
    except OSError:
        return 0
    if answer == "setup":
        subprocess.Popen(["sloth-center", "--page", "accounts"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
