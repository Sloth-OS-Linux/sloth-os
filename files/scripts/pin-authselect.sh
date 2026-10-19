#!/usr/bin/env bash
# PIN-kódos bejelentkezés: a Fedora "local" authselect-profiljából saját (vendor) profil, egyetlen új funkcióval
# (with-sloth-pin). Bekapcsolva a pam_unix elé egy pam_exec sor kerül (/usr/libexec/sloth-os/pin-check), és a
# pam_unix a már beírt jelszót használja (try_first_pass), hogy ne kérje kétszer. Kikapcsolva a profil
# ugyanaz, mint a "local". A profilt a Sloth Központ választja ki, amikor a felhasználó PIN-t állít be
# (sloth-helper pin-set), a meglévő funkciók (ujjlenyomat, biztonsági kulcs…) megtartásával.
set -euo pipefail

src=/usr/share/authselect/default/local
dst=/usr/share/authselect/vendor/sloth
[[ -d "$src" ]] || { echo "HIBA: nincs authselect local profil ($src)" >&2; exit 1; }
rm -rf "$dst"
mkdir -p "$(dirname "$dst")"
cp -a "$src" "$dst"

python3 - "$dst" <<'PYEOF'
import sys
from pathlib import Path

dst = Path(sys.argv[1])
unix = 'auth        sufficient                                   pam_unix.so {if not "without-nullok":nullok}\n'
pin = ('auth        sufficient                                   pam_exec.so quiet expose_authtok '
       '/usr/libexec/sloth-os/pin-check {include if "with-sloth-pin"}\n')
new_unix = ('auth        sufficient                                   pam_unix.so {if not "without-nullok":nullok} '
            '{if "with-sloth-pin":try_first_pass}\n')
for name in ("system-auth", "password-auth"):
    p = dst / name
    s = p.read_text()
    if s.count(unix) != 1:
        sys.exit(f"HIBA: a {name} pam_unix sora megváltozott, a PIN-sor nem illeszthető be")
    p.write_text(s.replace(unix, pin + new_unix))
readme = dst / "README"
text = readme.read_text().replace("Local users only\n================",
                                  "Sloth OS: local users (with optional PIN)\n=========================================", 1)
text = text.replace("AVAILABLE OPTIONAL FEATURES\n---------------------------\n",
                    "AVAILABLE OPTIONAL FEATURES\n---------------------------\n\n"
                    "with-sloth-pin::\n"
                    "    Enable sign-in with a numeric PIN (Sloth Center -> Account and security),\n"
                    "    checked by /usr/libexec/sloth-os/pin-check before pam_unix.\n", 1)
readme.write_text(text)
PYEOF
echo "authselect vendor profil: $dst (with-sloth-pin)"
