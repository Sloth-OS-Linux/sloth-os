#!/usr/bin/env bash
# Parental controls: the sign-in screen says why a child cannot sign in ("Your allowed hours haven't started yet.
# You can use the computer from 16:00."), not only "Login Failed".
#
# The screen time check (/usr/libexec/sloth-os/screen-time --may-sign-in, through pam_exec) sends the reason as a
# PAM information message, starting with an invisible mark (U+2063). plasma-login-manager's greeter shows it, then
# overwrites it with its own "Login Failed" at once (onLoginFailed in its Main.qml), and that QML is compiled into
# the greeter binary, so it cannot be changed as a file. This script rebuilds the greeter from Fedora's own source
# package of the installed version, with one change in Main.qml: a message that starts with the mark is kept, and
# shown in place of "Login Failed" until the next try. Every other failure looks exactly as before.
#
# The sign-in screen must never break because of this: anything unexpected (no source package for this exact
# version, Main.qml changed upstream, a failed build, the new greeter failing its test start where the stock one
# does not) leaves the stock greeter in place, with a warning in the build log. The build tools are removed again.
set -euo pipefail

PKG=plasma-login-manager
WORK=/tmp/greeter-build

nvr=$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}' "$PKG")
greeter=$(rpm -ql "$PKG" | grep -m1 '/plasma-login-greeter$')
[[ -x "$greeter" ]] || { echo "ERROR: no plasma-login-greeter in $PKG" >&2; exit 1; }

before=$(rpm -qa --qf '%{NAME}\n' | sort -u)

build() {
  set -euo pipefail
  mkdir -p "$WORK"
  cd "$WORK"
  dnf -y install --setopt=install_weak_deps=False rpm-build dnf5-plugins
  # the exact version that is installed, so the rebuilt greeter fits the rest of the package
  dnf -y download --srpm --enablerepo='fedora-source' --enablerepo='updates-source' --destdir="$WORK" "$nvr"
  srpm=$(ls "$WORK"/"$nvr".src.rpm)
  top="$WORK/rpmbuild"
  rpm -i --define "_topdir $top" "$srpm"
  spec=$(ls "$top"/SPECS/*.spec)
  dnf -y builddep --setopt=install_weak_deps=False "$spec"
  rpmbuild --define "_topdir $top" -bp --nodeps "$spec"

  main=$(find "$top/BUILD" -path '*/src/frontend/greeter/qml/Main.qml' | head -n1)
  [[ -f "$main" ]] || { echo "no greeter Main.qml in the source" >&2; return 1; }
  python3 - "$main" <<'PYEOF'
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
# the mark (U+2063, see /usr/libexec/sloth-os/screen-time), as a JavaScript escape in the QML source
mark = "\\" + "u2063"
s = p.read_text(encoding="utf-8")


def once(pattern, make):
    """Changes the one line that matches pattern (make: the match -> the new text)."""
    global s
    found = re.findall(pattern, s, flags=re.M)
    if len(found) != 1:
        sys.exit(f"Main.qml has changed: {pattern!r} found {len(found)} times")
    s = re.sub(pattern, make, s, count=1, flags=re.M)


# a reason from Sloth OS's screen time check, for this try only
once(r'^([ \t]*)property string notificationMessage[ \t]*$',
     lambda m: m[0] + "\n" + m[1] + 'property string slothReason: ""  // Sloth OS: why a child cannot sign in now')
# a new try forgets it
once(r'^([ \t]*)root\.notificationMessage = "";[ \t]*$',
     lambda m: m[0] + "\n" + m[1] + 'root.slothReason = "";')
# a message starting with the mark is the reason: kept, without the mark
once(r'^([ \t]*)function onInformationMessage\(message\) \{[ \t]*$',
     lambda m: "\n".join([m[0],
                          m[1] + '    if (message.startsWith("' + mark + '")) {',
                          m[1] + '        notificationResetTimer.stop();',
                          m[1] + '        root.slothReason = message.substring(1);',
                          m[1] + '        notificationMessage = root.slothReason;',
                          m[1] + '        return;',
                          m[1] + '    }']))
# shown instead of "Login Failed", and it stays until the next try
once(r'^([ \t]*)notificationMessage = ((?:KI18n\.)?i18nd\("plasma_login", "Login Failed"\));[ \t]*$',
     lambda m: m[1] + "notificationMessage = root.slothReason || " + m[2] + ";")
once(r'^([ \t]*)notificationResetTimer\.start\(\);[ \t]*$',
     lambda m: "\n".join([m[1] + "if (!root.slothReason) {", m[1] + "    notificationResetTimer.start();", m[1] + "}"]))
p.write_text(s, encoding="utf-8")
PYEOF
  grep -q 'notificationMessage = root.slothReason || ' "$main"

  # on from the patched source: %conf (cmake, the spec's own options), then %build
  rpmbuild --define "_topdir $top" -bf --short-circuit --nodeps "$spec"
  rpmbuild --define "_topdir $top" -bc --short-circuit --nocheck --nodeps "$spec"
  built=$(find "$top/BUILD" -type f -name plasma-login-greeter -perm -u+x | head -n1)
  [[ -x "$built" ]] || { echo "the build made no greeter" >&2; return 1; }

  # Test start (the greeter's own --test mode, offscreen): the new one must not show a QML error the stock one
  # does not (a typo in the change would leave a blank sign-in screen)
  qml_errors() {
    local run
    run=$(mktemp -d)
    chmod 700 "$run"
    XDG_RUNTIME_DIR="$run" QT_QPA_PLATFORM=offscreen timeout 15 "$1" --test 2>&1 >/dev/null \
      | grep -E 'Main\.qml:[0-9]+' | sed -E 's/^.*(Main\.qml:[0-9]+[^ ]*).*$/\1/' | sort -u || true
  }
  stock=$(qml_errors "$greeter")
  new=$(qml_errors "$built")
  if [[ -n "$(comm -13 <(echo "$stock") <(echo "$new"))" ]]; then
    echo "the rebuilt greeter's test start shows new QML errors:" >&2
    comm -13 <(echo "$stock") <(echo "$new") >&2
    return 1
  fi
  install -m 0755 "$built" "$greeter"
}

set +e
(build)
rc=$?
set -e

after=$(rpm -qa --qf '%{NAME}\n' | sort -u)
added=$(comm -13 <(echo "$before") <(echo "$after"))
if [[ -n "$added" ]]; then
  # shellcheck disable=SC2086
  dnf -y remove $added
fi
rm -rf "$WORK"
dnf clean all >/dev/null 2>&1 || true

if [[ $rc -ne 0 ]]; then
  echo "WARNING: the sign-in screen was not rebuilt (exit $rc); the stock greeter stays: a refused child sees" \
       "\"Login Failed\" without the reason" >&2
  exit 0
fi
echo "plasma-login-greeter rebuilt from $nvr with the screen time reason"
exit 0
