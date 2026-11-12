#!/usr/bin/bash
# The guest account (sloth-helper-family guest-on / guest-off, /usr/libexec/sloth-os/guest-reset) with real accounts,
# in a Fedora 44 container (the repository under /repo):
#   podman run --rm -v "$PWD":/repo:ro registry.fedoraproject.org/fedora:44 bash /repo/tools/tests/guest_test.sh
# There is no systemd or logind: guest-reset is run by hand where systemd would run it.
set -uo pipefail
dnf -q -y install python3-gobject shadow-utils passwd util-linux findutils >/dev/null 2>&1 || { echo "dnf failed"; exit 1; }
mkdir -p /usr/libexec/sloth-os /etc/skel
for f in sloth-helper sloth-helper-family guest-reset; do
    sed 's/\r$//' "/repo/files/system/usr/libexec/sloth-os/$f" > "/usr/libexec/sloth-os/$f"; chmod 755 "/usr/libexec/sloth-os/$f"
done
groupadd -f wheel && useradd -m -G wheel parent && echo "parent:pw" | chpasswd
echo "skel file" > /etc/skel/.welcome
# loginctl is not there: nobody is signed in
printf '#!/bin/sh\nexit 1\n' > /usr/local/bin/loginctl && chmod +x /usr/local/bin/loginctl
printf '#!/bin/sh\nexit 0\n' > /usr/local/bin/systemctl && chmod +x /usr/local/bin/systemctl
pass=0; fail=0
ok() { pass=$((pass+1)); echo "  OK:    $1"; }
bad() { fail=$((fail+1)); echo "  ERROR: $1"; }
expect() { local desc=$1 want=$2 out; shift 2; out=$("$@" 2>&1)
    if [[ $out == *"$want"* ]]; then ok "$desc"; else bad "$desc (expected: $want, got: $out)"; fi; }
PARENT_UID=$(id -u parent)
family() { local input=$1; shift; printf '%s' "$input" | PKEXEC_UID=$PARENT_UID /usr/libexec/sloth-os/sloth-helper-family "$@"; }

echo "== Turning it on"
expect "guest-on" '"ok": true' family '{"fullname": "Vendég"}' guest-on
expect "an ordinary account" "groups=$(id -g guest)(guest)" id guest
expect "its name" "Vendég" getent passwd guest
expect "no password (signs in with an empty one)" "guest NP" passwd -S guest
expect "the marker" "\"user\": \"guest\"" cat /etc/sloth-os/guest.json
expect "emptied when its last session ends, as root" "ExecStopPost=-+/usr/libexec/sloth-os/guest-reset --uid %i" \
    cat /repo/files/system/usr/lib/systemd/system/user@.service.d/50-sloth-guest.conf
[[ ! -e "/etc/systemd/system/user@$(id -u guest).service.d" ]] && ok "no per-user drop-in (it ran as the guest)" \
    || bad "per-user drop-in written"
expect "KDE's password store is off for the guest" "Enabled=false" cat /home/guest/.config/kwalletrc
[[ $(stat -c %U /home/guest/.config/kwalletrc) == guest ]] && ok "its own file" || bad "kwalletrc owner"
expect "again: nothing changes" '"ok": true' family '{"fullname": "Vendég"}' guest-on
expect "a bad name" '"bad input"' family '{"fullname": "a:b"}' guest-on
expect "no parental controls on the guest" '"not a child account"' family '{"daily": 3600}' child-limits guest

echo "== Emptied after use"
runuser -u guest -- sh -c 'echo secret > ~/notes.txt; mkdir -p ~/.config; echo x > ~/.config/app; echo t > /tmp/guest-left-this'
/usr/libexec/sloth-os/guest-reset --uid "$PARENT_UID"
[[ -e /home/guest/notes.txt ]] && ok "another user's sign-out leaves the guest alone" || bad "emptied for another user"
/usr/libexec/sloth-os/guest-reset --uid "$(id -u guest)"
[[ ! -e /home/guest/notes.txt && ! -e /home/guest/.config/app ]] && ok "its files are gone" || bad "files left: $(ls -A /home/guest)"
[[ -f /home/guest/.welcome ]] && ok "a fresh home from /etc/skel" || bad "no skel"
[[ $(stat -c %U:%a /home/guest) == guest:700 ]] && ok "still its own, private" || bad "owner/mode: $(stat -c %U:%a /home/guest)"
[[ ! -e /tmp/guest-left-this ]] && ok "its temporary files are gone" || bad "/tmp file left"
[[ -d /home/parent ]] && ok "the parent's home is untouched" || bad "parent home gone"

[[ $(grep -c Enabled=false /home/guest/.config/kwalletrc) == 1 ]] && ok "the password store stays off" || bad "kwalletrc"
mkdir -p "/etc/systemd/system/user@$(id -u guest).service.d"
echo old > "/etc/systemd/system/user@$(id -u guest).service.d/50-sloth-guest.conf"
/usr/libexec/sloth-os/guest-reset
[[ ! -e "/etc/systemd/system/user@$(id -u guest).service.d" ]] && ok "the old per-user drop-in goes at start" \
    || bad "old drop-in left"

echo "== Never someone else's account"
userdel -r guest; useradd -m guest  # the same free user ID as our guest had
echo "mine" > /home/guest/keep
expect "an account called guest that is not ours" '"exists"' family '{"fullname": "Guest"}' guest-on
/usr/libexec/sloth-os/guest-reset
[[ -f /home/guest/keep ]] && ok "guest-reset leaves it alone (same user ID, but it is not passwordless)" || bad "deleted someone's files"
userdel -r guest; rm -f /etc/sloth-os/guest.json

echo "== Turning it off"
expect "guest-on" '"ok": true' family '{"fullname": "Guest"}' guest-on
uid=$(id -u guest)
expect "guest-off" '"ok": true' family '' guest-off
id guest >/dev/null 2>&1 && bad "the account is still there" || ok "the account is gone"
[[ ! -e /home/guest ]] && ok "its home is gone" || bad "home left"
[[ ! -e /etc/sloth-os/guest.json && ! -e "/etc/systemd/system/user@$uid.service.d" ]] && ok "marker and drop-in gone" || bad "leftovers"
expect "guest-off again" '"ok": true' family '' guest-off
echo; echo "$pass OK, $fail ERROR"
[[ $fail == 0 ]]
