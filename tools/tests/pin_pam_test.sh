#!/usr/bin/bash
# A PIN-kódos bejelentkezés kipróbálása valódi PAM-mal, Fedora 44 konténerben (a repó a /repo alatt):
#   podman run --rm -v "$PWD":/repo:ro -v "$PWD/tools/tests/pin_pam_test.sh":/t.sh:ro registry.fedoraproject.org/fedora:44 bash /t.sh
set -uo pipefail
dnf -q -y install authselect pamtester python3 passwd util-linux >/dev/null 2>&1
install -m 755 /repo/files/system/usr/libexec/sloth-os/pin-check /usr/libexec/sloth-os/pin-check 2>/dev/null \
    || { mkdir -p /usr/libexec/sloth-os; install -m 755 /repo/files/system/usr/libexec/sloth-os/pin-check /usr/libexec/sloth-os/pin-check; }
install -m 755 /repo/files/system/usr/libexec/sloth-os/sloth-helper /tmp/sloth-helper
bash /repo/files/scripts/pin-authselect.sh
authselect select local --force >/dev/null
useradd -m tester && echo 'tester:Jelszo-123' | chpasswd
# egy távoli (ssh) és a zárolási képernyő (kde) PAM-szolgáltatása, ahogy a Fedorán
printf 'auth include password-auth\naccount include password-auth\n' > /etc/pam.d/sshd
printf 'auth include system-auth\naccount include system-auth\n' > /etc/pam.d/kde
printf 'auth include password-auth
account include password-auth
' > /etc/pam.d/plasmalogin

pass=0; fail=0
check() {  # leírás, várt (ok|nem), szolgáltatás, bevitel, [felhasználóként]
    local desc=$1 want=$2 svc=$3 input=$4 as=${5:-root} got
    if [[ $as == root ]]; then
        printf '%s\n' "$input" | pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=nem
    else
        printf '%s\n' "$input" | runuser -u tester -- pamtester "$svc" tester authenticate >/dev/null 2>&1 && got=ok || got=nem
    fi
    if [[ $got == "$want" ]]; then pass=$((pass+1)); echo "  rendben: $desc ($got)"; else fail=$((fail+1)); echo "  HIBA:    $desc (várt: $want, lett: $got)"; fi
}

echo "== PIN nélkül"
check "jelszó" ok plasmalogin 'Jelszo-123'
check "számjegyek, de nincs PIN" nem plasmalogin '482916'

echo "== PIN beállítása"
echo "1234" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set; echo
echo "482916" | PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-set; echo
echo "profil: $(authselect current --raw)"
stat -c '%U:%G %a %n' /etc/sloth-os/pin/tester.json

echo "== PIN-nel"
check "jó PIN (bejelentkezés)" ok plasmalogin '482916'
check "jelszó továbbra is" ok plasmalogin 'Jelszo-123'
check "rossz PIN" nem plasmalogin '000111'
check "rossz jelszó" nem plasmalogin 'rossz-jelszo'
check "PIN ssh-n (távoli)" nem sshd '482916'
check "jelszó ssh-n" ok sshd 'Jelszo-123'
check "jó PIN a zárolási képernyőn (felhasználóként)" ok kde '482916' user
check "jelszó a zárolási képernyőn (felhasználóként)" ok kde 'Jelszo-123' user

echo "== Sok hibás PIN"
for i in 1 2 3 4 5; do printf '99999%s\n' "$i" | pamtester plasmalogin tester authenticate >/dev/null 2>&1; done
check "jó PIN zárolás alatt" nem plasmalogin '482916'
check "jelszó zárolás alatt" ok plasmalogin 'Jelszo-123'
cat /var/lib/sloth-os/pin/tester.json; echo

echo "== PIN törlése"
PKEXEC_UID=$(id -u tester) /tmp/sloth-helper pin-remove; echo
echo "profil: $(authselect current --raw)"
check "volt PIN" nem plasmalogin '482916'
check "jelszó" ok plasmalogin 'Jelszo-123'
echo "== $pass rendben, $fail hiba"
