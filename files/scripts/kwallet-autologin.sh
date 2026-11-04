#!/usr/bin/env bash
# The password store (KWallet) opens by itself on an automatic sign-in too, when the disk is encrypted: the disk
# password typed at boot (the account's password by default, see the installer) is taken from root's keyring
# (pam_systemd_loadkey, systemd-cryptsetup keeps it there for 2.5 minutes) and handed to pam_kwallet, the same as a
# typed password on the normal sign-in. Without disk encryption there is nothing typed, so nothing changes: the
# wallet asks once, at its first use (an empty wallet password would leave the saved passwords readable on the disk).
# The two lines go into the vendor file, so its other updates stay; the service part is
# /usr/lib/systemd/system/plasmalogin.service.d/50-sloth-keyring.conf (KeyringMode=inherit).
set -euo pipefail

pam=/usr/lib/pam.d/plasmalogin-autologin
[[ -f "$pam" ]] || { echo "ERROR: no $pam" >&2; exit 1; }
python3 - "$pam" <<'PYEOF'
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
anchor = re.compile(r"^auth\s+include\s+postlogin\s*$", re.M)
if len(anchor.findall(s)) != 1:
    sys.exit(f"ERROR: the 'auth include postlogin' line of {p} has changed, the KWallet lines cannot be inserted")
lines = ("-auth      optional    pam_systemd_loadkey.so\n"
         "-auth      optional    pam_kwallet5.so\n"
         "-auth      optional    pam_kwallet.so\n")
if "pam_systemd_loadkey" not in s:
    s = anchor.sub(lambda m: lines + m.group(0), s, count=1)
    p.write_text(s)
PYEOF
grep -q pam_systemd_loadkey "$pam"
