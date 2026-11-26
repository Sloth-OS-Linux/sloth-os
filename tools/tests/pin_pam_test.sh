#!/usr/bin/bash
# PIN sign-in with real PAM, in a Fedora 44 container (the repository under /repo), twice: without a TPM (the
# root-only hash) and with a software TPM (swtpm: the PIN unlocks a secret sealed in the TPM):
#   podman run --rm -v "$PWD":/repo:ro registry.fedoraproject.org/fedora:44 bash /repo/tools/tests/pin_pam_test.sh
# There is no systemd here: pin-verifier --serve stands in for sloth-pin.socket.
set -uo pipefail
dnf -q -y install authselect pamtester python3 passwd util-linux procps-ng tpm2-tools swtpm swtpm-tools >/dev/null 2>&1 \
    || { echo "dnf failed"; exit 1; }
mkdir -p /usr/libexec/sloth-os /run/sloth-os /usr/src/sloth-os/pam_sloth_pin
# the PAM module, built by the image's own script (the profile's PIN line is pam_sloth_pin.so since 2026-11-26)
sed 's/\r$//' /repo/files/system/usr/src/sloth-os/pam_sloth_pin/pam_sloth_pin.c > /usr/src/sloth-os/pam_sloth_pin/pam_sloth_pin.c
sed 's/\r$//' /repo/files/scripts/pam-sloth-pin.sh | bash >/tmp/build.log 2>&1 || { echo "build failed"; tail -20 /tmp/build.log; exit 1; }
for f in pin-check pin-verifier; do
    sed 's/\r$//' "/repo/files/system/usr/libexec/sloth-os/$f" > "/usr/libexec/sloth-os/$f"
    chmod 755 "/usr/libexec/sloth-os/$f"
done
sed 's/\r$//' /repo/files/system/usr/libexec/sloth-os/sloth-helper > /tmp/sloth-helper && chmod 755 /tmp/sloth-helper
sed 's/\r$//' /repo/files/scripts/pin-authselect.sh | bash
authselect select local --force >/dev/null
useradd -m tester && echo 'tester:Password-123' | chpasswd
useradd -m other && echo 'other:Other-456' | chpasswd
# a remote (ssh) and the lock screen's (kde) PAM service, as on Fedora
printf 'auth include password-auth\naccount include password-auth\n' > /etc/pam.d/sshd
printf 'auth include system-auth\naccount include system-auth\n' > /etc/pam.d/kde
printf 'auth include password-auth\naccount include password-auth\n' > /etc/pam.d/plasmalogin

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  OK:    $1"; }
bad() { fail=$((fail+1)); echo "  ERROR: $1"; }
check() {  # description, expected (ok|no), service, input, [as the user]
    local desc=$1 want=$2 svc=$3 input=$4 as=${5:-root} got
    if [[ $as == root ]]; then
        printf '%s\n' "$input" | pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=no
    else
        printf '%s\n' "$input" | runuser -u tester -- pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=no
    fi
    [[ $got == "$want" ]] && ok "$desc ($got)" || bad "$desc (expected: $want, got: $got)"
}
ask_as() {  # user to run as, whose PIN, PIN -> the socket's answer
    runuser -u "$1" -- python3 -c '
import json, socket, sys
s = socket.socket(socket.AF_UNIX); s.connect("/run/sloth-os/pin.sock")
s.sendall(json.dumps({"user": sys.argv[1], "pin": sys.argv[2], "service": "kde"}).encode() + b"\n")
print(s.recv(16).decode().strip())' "$2" "$3"
}
status_as() {  # user to run as, whose PIN -> the socket's answer to "is a PIN set?" (what Sloth Center asks)
    runuser -u "$1" -- python3 -c '
import json, socket, sys
s = socket.socket(socket.AF_UNIX); s.connect("/run/sloth-os/pin.sock")
s.sendall(json.dumps({"user": sys.argv[1], "status": True}).encode() + b"\n")
print(s.recv(64).decode().strip())' "$2"
}
start_verifier() {
    pkill -f "pin-verifier --serve" 2>/dev/null; sleep 0.3
    /usr/libexec/sloth-os/pin-verifier --serve /run/sloth-os/pin.sock 2>>/tmp/verifier.log &
    for _ in $(seq 50); do [[ -S /run/sloth-os/pin.sock ]] && break; sleep 0.1; done
}

run_round() {  # the round's name
    echo "######## $1"
    rm -rf /etc/sloth-os/pin /var/lib/sloth-os/pin
    start_verifier
    echo "== Without a PIN"
    check "password" ok plasmalogin 'Password-123'
    check "digits, but no PIN" no plasmalogin '482916'

    echo "== Setting a PIN"
    r=$(echo "1234" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set)
    [[ $r == *'weak PIN'* ]] && ok "a weak PIN is refused" || bad "weak PIN: $r"
    r=$(echo "482916" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set)
    [[ $r == *'"ok": true'* ]] && ok "PIN set: $r" || bad "PIN set: $r"
    perms=$(stat -c '%U:%G %a' /etc/sloth-os/pin/tester.json)
    [[ $perms == "root:root 600" ]] && ok "the PIN's file is root's only" || bad "file rights: $perms"
    if [[ $1 == TPM ]]; then
        [[ $r == *'"tpm": true'* ]] && ok "sealed in the TPM" || bad "not in the TPM"
        grep -q '"hash"' /etc/sloth-os/pin/tester.json && bad "a hash is stored with a TPM" || ok "nothing to guess on the disk (no hash)"
        [[ -f /etc/sloth-os/pin/tester.tpm/seal.priv ]] && ok "the sealed object is there" || bad "no sealed object"
    else
        [[ $r == *'"tpm": false'* ]] && ok "no TPM: the root-only hash" || bad "tpm flag: $r"
    fi
    st=$(status_as tester tester)
    want='{"set": true, "tpm": false, "wallet": false}'; [[ $1 == TPM ]] && want='{"set": true, "tpm": true, "wallet": false}'
    [[ $st == "$want" ]] && ok "Sloth Center (as the user) learns the PIN is set: $st" || bad "status: $st"
    [[ $(status_as other tester) == no ]] && ok "another user does not learn it" || bad "another user's status answer"
    runuser -u tester -- cat /etc/sloth-os/pin/tester.json >/dev/null 2>&1 && bad "the user can read the PIN's file" \
        || ok "the user cannot read the PIN's file"

    echo "== With the PIN"
    check "right PIN (login)" ok plasmalogin '482916'
    check "password still works" ok plasmalogin 'Password-123'
    check "wrong PIN" no plasmalogin '000111'
    check "wrong password" no plasmalogin 'wrong-password'
    check "PIN over ssh (remote)" no sshd '482916'
    check "password over ssh" ok sshd 'Password-123'
    check "right PIN on the lock screen (as the user)" ok kde '482916' user
    check "password on the lock screen (as the user)" ok kde 'Password-123' user
    [[ $(ask_as other tester 482916) == no ]] && ok "another user cannot test this user's PIN" \
        || bad "another user could test the PIN"
    [[ $(ask_as tester tester 482916) == ok ]] && ok "the user can check their own" || bad "own check failed"

    echo "== Many wrong PINs"
    for i in 1 2 3 4 5; do printf '99999%s\n' "$i" | pamtester plasmalogin tester authenticate >/dev/null 2>&1; done
    [[ -n ${TPM2TOOLS_TCTI:-} ]] && echo "    the TPM's own count: $(tpm2_getcap properties-variable 2>/dev/null | grep -iE 'lockoutCounter|inLockout' -A0 | tr -s ' ' | tr '
' ' ')"
    check "right PIN while locked out" no plasmalogin '482916'
    check "password while locked out" ok plasmalogin 'Password-123'
    perms=$(stat -c '%U %a' /var/lib/sloth-os/pin/tester.json)
    [[ $perms == "root 600" ]] && ok "the wrong tries are counted by root (the user cannot reset them)" \
        || bad "count file: $perms"
    rm -f /var/lib/sloth-os/pin/tester.json
    check "after the wait, the right PIN again" ok plasmalogin '482916'

    echo "== Removing the PIN"
    PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-remove >/dev/null
    check "former PIN" no plasmalogin '482916'
    check "password" ok plasmalogin 'Password-123'
    [[ ! -e /etc/sloth-os/pin/tester.tpm ]] && ok "the sealed object is gone too" || bad "sealed object left"
}

# 1. without a TPM
unset TPM2TOOLS_TCTI
run_round "no TPM"

# 2. with a software TPM
mkdir -p /tmp/tpm
swtpm socket --tpm2 --tpmstate dir=/tmp/tpm --server type=tcp,port=2321 --ctrl type=tcp,port=2322 \
    --flags not-need-init,startup-clear >/tmp/swtpm.log 2>&1 &
sleep 1
export TPM2TOOLS_TCTI="swtpm:host=127.0.0.1,port=2321"
tpm2_startup -c >/dev/null 2>&1
# a real PC's TPM usually allows 32 wrong tries (swtpm's own default is 3): our own count (5 free) comes first
tpm2_dictionarylockout -s -n 32 -t 600 -l 600 >/dev/null 2>&1
run_round TPM

echo "== A PIN set before (v1: scrypt, readable by the user's group) moves into the TPM"
rm -rf /etc/sloth-os/pin /var/lib/sloth-os/pin
start_verifier
mkdir -p /etc/sloth-os/pin
python3 - <<'EOF'
import hashlib, json, secrets
salt = secrets.token_bytes(16)
d = hashlib.scrypt(b"482916", salt=salt, n=2 ** 15, r=8, p=1, maxmem=128 * 1024 * 1024, dklen=32)
json.dump({"v": 1, "salt": salt.hex(), "hash": d.hex(), "len": 6, "n": 2 ** 15, "r": 8, "p": 1},
          open("/etc/sloth-os/pin/tester.json", "w"))
EOF
authselect select sloth with-sloth-pin --force >/dev/null
check "the old PIN works" ok plasmalogin '482916'
grep -q '"v": 2' /etc/sloth-os/pin/tester.json && ok "now sealed in the TPM" || bad "not moved: $(cat /etc/sloth-os/pin/tester.json)"
check "and works from the TPM" ok plasmalogin '482916'

echo "== The TPM locked out by wrong tries (as after many guesses): the PIN waits, the password works"
tpm2_dictionarylockout -s -n 2 -t 600 -l 600 >/dev/null 2>&1
for i in 1 2 3; do printf '11111%s
' "$i" | pamtester plasmalogin tester authenticate >/dev/null 2>&1; done
echo "    the TPM: $(tpm2_getcap properties-variable 2>/dev/null | grep -i inLockout | tr -s ' ')"
rm -f /var/lib/sloth-os/pin/tester.json            # our own count cleared: only the TPM says no now
check "the right PIN while the TPM is locked out" no plasmalogin '482916'
check "the password while the TPM is locked out" ok plasmalogin 'Password-123'
r=$(echo "482916" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set)
[[ $r == *'"tpm": true'* ]] && ok "a new PIN can still be sealed (the storage key is not counted)" || bad "sealing while locked out: $r"
tpm2_dictionarylockout -c >/dev/null 2>&1          # the owner clears the lockout (or the time passes)
check "after the lockout, the PIN again" ok plasmalogin '482916'

pkill -f "pin-verifier --serve"; pkill swtpm
echo "== $pass OK, $fail errors"
[[ $fail == 0 ]]
