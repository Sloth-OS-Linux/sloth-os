#!/usr/bin/env bash
# PIN sign-in: builds pam_sloth_pin.so (files/system/usr/src/sloth-os/pam_sloth_pin), the PAM module that checks the
# PIN and, on the sign-in screen, hands the account's password on to KWallet (see the source). The "sloth" authselect
# profile uses it (pin-authselect.sh). The build tools are removed again and so is the source.
# Runs before kcmhost.sh, which removes the whole /usr/src/sloth-os.
set -euo pipefail

SRC=/usr/src/sloth-os/pam_sloth_pin
DEST=/usr/lib64/security/pam_sloth_pin.so

before=$(rpm -qa --qf '%{NAME}\n' | sort -u)
dnf -y install --setopt=install_weak_deps=False gcc pam-devel
after=$(rpm -qa --qf '%{NAME}\n' | sort -u)
added=$(comm -13 <(echo "$before") <(echo "$after"))

gcc -O2 -Wall -Wextra -Werror -fPIC -shared -fstack-protector-strong -D_FORTIFY_SOURCE=2 -Wl,-z,relro,-z,now \
  -o /tmp/pam_sloth_pin.so "$SRC/pam_sloth_pin.c" -lpam
install -m 0755 /tmp/pam_sloth_pin.so "$DEST"
rm -f /tmp/pam_sloth_pin.so

if [[ -n "$added" ]]; then
  # shellcheck disable=SC2086
  dnf -y remove $added
fi
rm -rf "$SRC"

# The module must load: a PAM stack naming a module that cannot be loaded would refuse every sign-in with a PIN
python3 - "$DEST" <<'PYEOF'
import ctypes
import sys
lib = ctypes.CDLL(sys.argv[1])
assert lib.pam_sm_authenticate and lib.pam_sm_setcred
PYEOF
echo "pam_sloth_pin: $DEST"
