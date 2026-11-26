#!/usr/bin/bash
# The PIN opens the password store (KWallet) at sign-in: real PAM with the real pam_sloth_pin.so (built here like in
# the image), pin-verifier, and a software TPM (swtpm), in a Fedora 44 container (the repository under /repo):
#   podman run --rm -v "$PWD":/repo:ro registry.fedoraproject.org/fedora:44 bash /repo/tools/tests/pin_wallet_test.sh
# After the sign-in stack a pam_exec step writes down PAM_AUTHTOK: that is exactly what pam_kwallet would get. The
# right PIN on the sign-in screen (root, plasmalogin) must turn it into the account's password; nowhere else.
set -uo pipefail
dnf -q -y install authselect pamtester python3 passwd util-linux procps-ng tpm2-tools swtpm swtpm-tools gcc pam-devel \
    >/dev/null 2>&1 || { echo "dnf failed"; exit 1; }
mkdir -p /usr/libexec/sloth-os /run/sloth-os /usr/src/sloth-os/pam_sloth_pin
sed 's/\r$//' /repo/files/system/usr/libexec/sloth-os/pin-verifier > /usr/libexec/sloth-os/pin-verifier
chmod 755 /usr/libexec/sloth-os/pin-verifier
sed 's/\r$//' /repo/files/system/usr/src/sloth-os/pam_sloth_pin/pam_sloth_pin.c > /usr/src/sloth-os/pam_sloth_pin/pam_sloth_pin.c
# the image's build script (it also removes gcc and pam-devel again, as in the image: dnf keeps what it found before)
sed 's/\r$//' /repo/files/scripts/pam-sloth-pin.sh | bash >/tmp/build.log 2>&1 || { echo "build failed"; tail -20 /tmp/build.log; exit 1; }
sed 's/\r$//' /repo/files/scripts/pin-authselect.sh | bash
authselect select sloth with-sloth-pin --force >/dev/null
useradd -m tester && echo 'tester:Password-123' | chpasswd

cat > /usr/local/bin/capture-authtok <<'EOF'
#!/usr/bin/bash
tr -d '\0' > /tmp/authtok.out
EOF
chmod 755 /usr/local/bin/capture-authtok
for svc in plasmalogin kde sudo; do
    printf 'auth substack password-auth\nauth optional pam_exec.so expose_authtok /usr/local/bin/capture-authtok\naccount include password-auth\n' \
        > /etc/pam.d/$svc
done

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  OK:    $1"; }
bad() { fail=$((fail+1)); echo "  ERROR: $1"; }
signin() {  # service, typed text, [as the user] -> "ok <what pam_kwallet would get>" or "no"
    rm -f /tmp/authtok.out
    local r
    if [[ ${3:-root} == root ]]; then
        printf '%s\n' "$2" | pamtester "$1" tester authenticate >/dev/null 2>&1 && r=ok || r=no
    else
        chmod 777 /tmp
        printf '%s\n' "$2" | runuser -u tester -- pamtester "$1" tester authenticate >/dev/null 2>&1 && r=ok || r=no
    fi
    [[ $r == ok ]] && echo "ok $(cat /tmp/authtok.out 2>/dev/null)" || echo no
}
expect() {  # description, expected, got
    [[ $3 == "$2" ]] && ok "$1 ($3)" || bad "$1 (expected: $2, got: $3)"
}
set_pin() {  # PIN, password -> pin-verifier's answer
    printf '%s\n%s\n' "$1" "$2" | /usr/libexec/sloth-os/pin-verifier --set tester 2>/dev/null | tail -1
}
status() {
    runuser -u tester -- python3 -c '
import json, socket
s = socket.socket(socket.AF_UNIX); s.connect("/run/sloth-os/pin.sock")
s.sendall(json.dumps({"user": "tester", "status": True}).encode() + b"\n")
print(s.recv(128).decode().strip())'
}
start_verifier() {
    pkill -f "pin-verifier --serve" 2>/dev/null; sleep 0.3
    /usr/libexec/sloth-os/pin-verifier --serve /run/sloth-os/pin.sock 2>>/tmp/verifier.log &
    for _ in $(seq 50); do [[ -S /run/sloth-os/pin.sock ]] && break; sleep 0.1; done
}

echo "== The module is built and in the profile"
[[ -f /usr/lib64/security/pam_sloth_pin.so ]] && ok "pam_sloth_pin.so built" || bad "pam_sloth_pin.so missing"
grep -q pam_sloth_pin.so /etc/authselect/password-auth && ok "password-auth uses pam_sloth_pin.so" \
    || bad "password-auth: $(grep -n 'sloth\|pin' /etc/authselect/password-auth)"
grep -q pin-check /etc/authselect/password-auth && bad "pin-check still in password-auth" || ok "no pam_exec pin-check line"
rpm -q gcc >/dev/null 2>&1 && echo "  (gcc was there before the build, so it stays: fine in this container)"

# --- with a software TPM ------------------------------------------------------------------------
mkdir -p /tmp/tpm
swtpm socket --tpm2 --tpmstate dir=/tmp/tpm --server type=tcp,port=2321 --ctrl type=tcp,port=2322 \
    --flags not-need-init,startup-clear >/tmp/swtpm.log 2>&1 &
sleep 1
export TPM2TOOLS_TCTI="swtpm:host=127.0.0.1,port=2321"
tpm2_startup -c >/dev/null 2>&1
tpm2_dictionarylockout -s -n 32 -t 600 -l 600 >/dev/null 2>&1
start_verifier

echo "== TPM: setting the PIN with the password"
expect "a wrong password is refused" '{"ok": false, "error": "bad password"}' "$(set_pin 2580 Wrong-999)"
expect "the right password is kept" '{"ok": true, "tpm": true, "wallet": true}' "$(set_pin 2580 Password-123)"
expect "Sloth Center sees it" '{"set": true, "tpm": true, "wallet": true, "dropped": false}' "$(status)"
ls -l /etc/sloth-os/pin/tester.json | grep -q '^-rw-------' && ok "the record is root-only" || bad "record rights: $(ls -l /etc/sloth-os/pin/tester.json)"
grep -q "Password-123" /etc/sloth-os/pin/tester.json && bad "the password is in the record in the clear" || ok "the password is not in the record in the clear"

echo "== TPM: signing in"
expect "sign-in screen, right PIN: pam_kwallet gets the password" "ok Password-123" "$(signin plasmalogin 2580)"
expect "sign-in screen, wrong PIN" "no" "$(signin plasmalogin 1470)"
expect "sign-in screen, the password itself" "ok Password-123" "$(signin plasmalogin Password-123)"
expect "lock screen (in the user's name), right PIN: no password back" "ok 2580" "$(signin kde 2580 tester)"
expect "sudo (root, not a sign-in screen), right PIN: no password back" "ok 2580" "$(signin sudo 2580)"

echo "== TPM: a caller in the user's name asking for the password itself"
got=$(runuser -u tester -- python3 -c '
import json, socket
s = socket.socket(socket.AF_UNIX); s.connect("/run/sloth-os/pin.sock")
s.sendall(json.dumps({"user": "tester", "pin": "2580", "service": "plasmalogin", "authtok": True}).encode() + b"\n")
print(s.recv(256).decode().strip())')
expect "only ok, never the password" "ok" "$got"

echo "== TPM: the password changed (e.g. in KDE's Users page)"
echo 'tester:Changed-456' | chpasswd
expect "the PIN still signs in, the old password is not handed on" "ok 2580" "$(signin plasmalogin 2580)"
expect "the old copy is dropped" '{"set": true, "tpm": true, "wallet": false, "dropped": true}' "$(status)"
expect "set again with the new password" '{"ok": true, "tpm": true, "wallet": true}' "$(set_pin 2580 Changed-456)"
expect "and the PIN opens the store again" "ok Changed-456" "$(signin plasmalogin 2580)"

echo "== TPM: setting the PIN without a password (as before)"
expect "no password: nothing kept" '{"ok": true, "tpm": true, "wallet": false}' "$(set_pin 2580 '')"
expect "the PIN signs in, the store asks once (as before)" "ok 2580" "$(signin plasmalogin 2580)"

echo "== TPM: a password with spaces and accents"
echo 'tester:Héllo wörld 7!' | chpasswd
expect "kept" '{"ok": true, "tpm": true, "wallet": true}' "$(set_pin 3691 'Héllo wörld 7!')"
expect "handed on as it is" "ok Héllo wörld 7!" "$(signin plasmalogin 3691)"

# --- without a TPM ------------------------------------------------------------------------------
pkill -f "pin-verifier --serve"; pkill swtpm; sleep 0.5
unset TPM2TOOLS_TCTI
rm -rf /etc/sloth-os/pin /var/lib/sloth-os/pin
start_verifier
echo "== No TPM: the password is checked but never kept (a short PIN would guard a copy on the disk)"
expect "set with the password" '{"ok": true, "tpm": false, "wallet": false}' "$(set_pin 2580 'Héllo wörld 7!')"
expect "the PIN signs in, no password handed on" "ok 2580" "$(signin plasmalogin 2580)"
grep -q wallet /etc/sloth-os/pin/tester.json && bad "a wallet copy without a TPM" || ok "no copy in the record"

pkill -f "pin-verifier --serve"
echo
echo "Result: $pass OK, $fail errors"
[[ -s /tmp/verifier.log ]] && { echo "--- pin-verifier log:"; cat /tmp/verifier.log; }
[[ $fail -eq 0 ]]
