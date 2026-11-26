#!/usr/bin/env bash
# PIN sign-in: our own (vendor) profile made from Fedora's "local" authselect profile, with a single new feature
# (with-sloth-pin). When on, pam_sloth_pin.so goes before pam_unix (built by pam-sloth-pin.sh; it checks the PIN and
# on the sign-in screen hands the password on to KWallet), and pam_unix uses the text already typed
# (try_first_pass), so it does not ask twice. (Before 2026-11-26 the line was pam_exec + pin-check, which could not
# open KWallet; systems that chose the profile then keep that until Sloth Center applies the profile again.) When off, the profile is
# the same as "local". Sloth Center selects the profile when the user sets a PIN
# (sloth-helper pin-set), keeping the existing features (fingerprint, security key…).
set -euo pipefail

src=/usr/share/authselect/default/local
dst=/usr/share/authselect/vendor/sloth
[[ -d "$src" ]] || { echo "ERROR: no authselect local profile ($src)" >&2; exit 1; }
rm -rf "$dst"
mkdir -p "$(dirname "$dst")"
cp -a "$src" "$dst"

python3 - "$dst" <<'PYEOF'
import sys
from pathlib import Path

dst = Path(sys.argv[1])
unix = 'auth        sufficient                                   pam_unix.so {if not "without-nullok":nullok}\n'
pin = ('auth        sufficient                                   pam_sloth_pin.so                                       '
       '{include if "with-sloth-pin"}\n')
new_unix = ('auth        sufficient                                   pam_unix.so {if not "without-nullok":nullok} '
            '{if "with-sloth-pin":try_first_pass}\n')
for name in ("system-auth", "password-auth"):
    p = dst / name
    s = p.read_text()
    if s.count(unix) != 1:
        sys.exit(f"ERROR: the pam_unix line of {name} has changed, the PIN line cannot be inserted")
    p.write_text(s.replace(unix, pin + new_unix))
readme = dst / "README"
text = readme.read_text().replace("Local users only\n================",
                                  "Sloth OS: local users (with optional PIN)\n=========================================", 1)
text = text.replace("AVAILABLE OPTIONAL FEATURES\n---------------------------\n",
                    "AVAILABLE OPTIONAL FEATURES\n---------------------------\n\n"
                    "with-sloth-pin::\n"
                    "    Enable sign-in with a numeric PIN (Sloth Center -> Account and security),\n"
                    "    checked by pam_sloth_pin.so before pam_unix.\n", 1)
readme.write_text(text)
PYEOF
echo "authselect vendor profil: $dst (with-sloth-pin)"
