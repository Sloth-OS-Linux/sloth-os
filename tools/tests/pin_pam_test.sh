#!/usr/bin/bash
# Trying PIN sign-in with real PAM, in a Fedora 44 container (the repository under /repo):
#   podman run --rm -v "$PWD":/repo:ro -v "$PWD/tools/tests/pin_pam_test.sh":/t.sh:ro registry.fedoraproject.org/fedora:44 bash /t.sh
set -uo pipefail
dnf -q -y install authselect pamtester python3 passwd util-linux >/dev/null 2>&1
install -m 755 /repo/files/system/usr/libexec/sloth-os/pin-check /usr/libexec/sloth-os/pin-check 2>/dev/null \
    || { mkdir -p /usr/libexec/sloth-os; install -m 755 /repo/files/system/usr/libexec/sloth-os/pin-check /usr/libexec/sloth-os/pin-check; }
install -m 755 /repo/files/system/usr/libexec/sloth-os/sloth-helper /tmp/sloth-helper
bash /repo/files/scripts/pin-authselect.sh
authselect select local --force >/dev/null
useradd -m tester && echo 'tester:Password-123' | chpasswd
# a remote (ssh) and the lock screen's (kde) PAM service, as on Fedora
printf 'auth include password-auth\naccount include password-auth\n' > /etc/pam.d/sshd
printf 'auth include system-auth\naccount include system-auth\n' > /etc/pam.d/kde
printf 'auth include password-auth
account include password-auth
' > /etc/pam.d/plasmalogin

pass=0; fail=0
check() {  # description, expected (ok|no), service, input, [as the user]
    local desc=$1 want=$2 svc=$3 input=$4 as=${5:-root} got
    if [[ $as == root ]]; then
        printf '%s\n' "$input" | pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=no
    else
        printf '%s\n' "$input" | runuser -u tester -- pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=no
    fi
    if [[ $got == "$want" ]]; then pass=$((pass+1)); echo "  OK:    $desc ($got)"; else fail=$((fail+1)); echo "  ERROR: $desc (expected: $want, got: $got)"; fi
}

echo "== Without a PIN"
check "password" ok plasmalogin 'Password-123'
check "digits, but no PIN" no plasmalogin '482916'

echo "== Setting a PIN"
echo "1234" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set; echo
echo "482916" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set; echo
echo "profil: $(authselect current --raw)"
stat -c '%U:%G %a %n' /etc/sloth-os/pin/tester.json

echo "== PIN-nel"
check "right PIN (login)" ok plasmalogin '482916'
check "password still works" ok plasmalogin 'Password-123'
check "wrong PIN" no plasmalogin '000111'
check "wrong password" no plasmalogin 'wrong-password'
check "PIN over ssh (remote)" no sshd '482916'
check "password over ssh" ok sshd 'Password-123'
check "right PIN on the lock screen (as the user)" ok kde '482916' user
check "password on the lock screen (as the user)" ok kde 'Password-123' user

echo "== Many wrong PINs"
for i in 1 2 3 4 5; do printf '99999%s\n' "$i" | pamtester plasmalogin tester authenticate >/dev/null 2>&1; done
check "right PIN while locked out" no plasmalogin '482916'
check "password while locked out" ok plasmalogin 'Password-123'
cat /var/lib/sloth-os/pin/tester.json; echo

echo "== Removing the PIN"
PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-remove; echo
echo "profil: $(authselect current --raw)"
check "former PIN" no plasmalogin '482916'
check "password" ok plasmalogin 'Password-123'
echo "== $pass OK, $fail errors"
