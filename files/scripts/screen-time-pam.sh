#!/usr/bin/env bash
# Parental controls: outside a child's allowed hours, or with the day's screen time used up, the sign-in screen does
# not let the child in (Sloth Center → Parental controls; /usr/libexec/sloth-os/screen-time --may-sign-in, which
# prints the reason and when the computer can be used again). Administrators skip the check altogether (the
# pam_succeed_if line jumps over it), so nothing in it can ever lock a parent out; for a child anything unexpected
# in the check lets them in, and the screen time service signs them out again if their time is really over.
# The lines go into the vendor files before their "account include password-auth", so their other updates stay.
set -euo pipefail

for pam in /usr/lib/pam.d/plasmalogin /usr/lib/pam.d/plasmalogin-autologin; do
    [[ -f "$pam" ]] || { echo "ERROR: no $pam" >&2; exit 1; }
    python3 - "$pam" <<'PYEOF'
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
anchor = re.compile(r"^account\s+include\s+password-auth\s*$", re.M)
if len(anchor.findall(s)) != 1:
    sys.exit(f"ERROR: the 'account include password-auth' line of {p} has changed, the screen time check cannot go in")
lines = ("account    [success=1 default=ignore] pam_succeed_if.so quiet user ingroup wheel\n"
         "account    required    pam_exec.so quiet stdout /usr/libexec/sloth-os/screen-time --may-sign-in\n")
if "screen-time --may-sign-in" not in s:
    s = anchor.sub(lambda m: lines + m.group(0), s, count=1)
    p.write_text(s)
PYEOF
    grep -q "screen-time --may-sign-in" "$pam"
done
