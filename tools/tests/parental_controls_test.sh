#!/usr/bin/bash
# Parental controls' system side with the real services, in a Fedora 44 container (the repository under /repo):
#   podman run --rm -v "$PWD":/repo:ro registry.fedoraproject.org/fedora:44 bash /repo/tools/tests/parental_controls_test.sh
# There is no systemd or logind in the container: dbus, polkitd, accounts-daemon and malcontent-timerd are started by
# hand, and the screen time service gets a fake session list (logind). sloth-helper-family writes the settings into
# AccountsService (malcontent), screen-time records and reads the usage in the child's name (malcontent-timerd).
set -uo pipefail
dnf -q -y install malcontent malcontent-tools accountsservice polkit dbus-daemon python3-gobject shadow-utils \
    systemd passwd util-linux >/dev/null 2>&1 || { echo "dnf failed"; exit 1; }
mkdir -p /usr/libexec/sloth-os
for f in sloth-helper sloth-helper-family screen-time; do
    sed 's/\r$//' "/repo/files/system/usr/libexec/sloth-os/$f" > "/usr/libexec/sloth-os/$f"
    chmod 755 "/usr/libexec/sloth-os/$f"
done
systemd-sysusers >/dev/null 2>&1
groupadd -f wheel
useradd -m -G wheel parent && echo "parent:pw" | chpasswd
TIMERD_USER=$(awk '$1 == "u" {print $2}' /usr/lib/sysusers.d/malcontent-timerd.conf)
# without systemd, timerd's process has no unit: malcontent's own rule (subject.system_unit) does not match it
cat > /etc/polkit-1/rules.d/00-test.rules <<EOF
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("com.endlessm.ParentalControls.SessionLimits.") == 0 && subject.user == "$TIMERD_USER")
        return polkit.Result.YES;
});
EOF
mkdir -p /run/dbus /var/lib/malcontent-timerd
dbus-daemon --system --fork
/usr/lib/polkit-1/polkitd --no-debug >/tmp/polkitd.log 2>&1 &
sleep 1
/usr/libexec/accounts-daemon >/tmp/accounts.log 2>&1 &
sleep 1
chown "$TIMERD_USER" /var/lib/malcontent-timerd
STATE_DIRECTORY=/var/lib/malcontent-timerd setpriv --reuid "$TIMERD_USER" --regid "$TIMERD_USER" --clear-groups \
    /usr/libexec/malcontent-timerd >/tmp/timerd.log 2>&1 &
sleep 2

pass=0; fail=0
ok() { pass=$((pass+1)); echo "  OK:    $1"; }
bad() { fail=$((fail+1)); echo "  ERROR: $1"; }
expect() {  # description, expected text in the output, command...
    local desc=$1 want=$2 out; shift 2
    out=$("$@" 2>&1)
    if [[ $out == *"$want"* ]]; then ok "$desc"; else bad "$desc (expected: $want, got: $out)"; fi
}
PARENT_UID=$(id -u parent)
family() { local input=$1; shift; printf '%s' "$input" | PKEXEC_UID=$PARENT_UID /usr/libexec/sloth-os/sloth-helper-family "$@"; }

echo "== A child account"
expect "child-add" '"ok": true' family '{"username": "anna", "fullname": "Anna Kis", "password": "secret1"}' child-add
expect "an ordinary account, not in wheel" "groups=$(id -g anna)(anna)" id anna
expect "the same name again" '"exists"' family '{"username": "anna", "fullname": "A", "password": "x"}' child-add
expect "it cannot install apps by itself" "disallowed to user repository" malcontent-client get-app-filter anna

echo "== Refused"
expect "a bad username" '"bad input"' family '{"username": "Anna!", "fullname": "A", "password": "x"}' child-add
expect "a colon in the name" '"bad input"' family '{"username": "bob", "fullname": "A:b", "password": "x"}' child-add
expect "limits on an administrator" '"not a child account"' family '{"daily": 3600}' child-limits parent
expect "limits on root" '"not a child account"' family '{"daily": 3600}' child-limits root
expect "a negative limit" '"bad input"' family '{"daily": -5}' child-limits anna
expect "the end before the start" '"bad input"' family '{"daily": 0, "start": 7200, "end": 3600}' child-limits anna
expect "not a Flatpak ref" '"bad input"' family '{"blocked": ["app/../../x/y"]}' child-apps anna
expect "child-* through the plain helper" '"unknown operation"' \
    env PKEXEC_UID="$PARENT_UID" /usr/libexec/sloth-os/sloth-helper child-limits anna
expect "other operations through the family helper" '"unknown operation"' \
    env PKEXEC_UID="$PARENT_UID" /usr/libexec/sloth-os/sloth-helper-family zram off

echo "== Screen time and apps"
expect "child-limits" '"ok": true' family '{"daily": 3600, "start": 0, "end": 86400}' child-limits anna
expect "the daily limit is in malcontent" "equals 3600s per day" malcontent-client get-session-limits anna
expect "child-apps" '"ok": true' \
    family '{"blocked": ["app/org.mozilla.firefox/x86_64/stable", "app/com.valvesoftware.Steam/x86_64/stable"]}' child-apps anna
expect "Firefox is blocked" "is not allowed" malcontent-client check-app-filter anna app/org.mozilla.firefox/x86_64/stable
expect "KCalc is allowed" "is allowed" malcontent-client check-app-filter anna app/org.kde.kcalc/x86_64/stable
[[ -s /run/sloth-os/family/anna.apps ]] && ok "the child's session is told (anna.apps)" || bad "no anna.apps"
# what sloth-exe asks (Windows programs and AppImages), with the real malcontent through GObject introspection
programs() { setpriv --reuid anna --regid anna --clear-groups python3 -I -c '
import gi; gi.require_version("Malcontent", "0"); from gi.repository import Gio, Malcontent
m = Malcontent.Manager.new(Gio.bus_get_sync(Gio.BusType.SYSTEM, None))
f = m.get_app_filter(__import__("os").getuid(), Malcontent.ManagerGetValueFlags.NONE, None)
print("programs", f.is_content_type_allowed("application/x-ms-dos-executable"),
      "firefox", f.is_flatpak_app_allowed("org.mozilla.firefox"))'; }
expect "Windows programs allowed until turned off (read as the child)" "programs True firefox False" programs
expect "Windows programs off" '"ok": true' \
    family '{"blocked": ["app/org.mozilla.firefox/x86_64/stable"], "programs": false}' child-apps anna
expect "sloth-exe's question says no, the blocked app stays blocked" "programs False firefox False" programs
expect "a new child starts with the web filter on" '"anna"' cat /etc/sloth-os/family-web.json
expect "child-web off" '"ok": false' family '' child-web anna off  # family-web cannot run here (no nft)
expect "but the list is saved" '"users": []' cat /etc/sloth-os/family-web.json

echo "== The screen time service, with the real malcontent-timerd"
out=$(python3 -I - <<'EOF'
import importlib.machinery, importlib.util, os, pwd, time
loader = importlib.machinery.SourceFileLoader("st", "/usr/libexec/sloth-os/screen-time")
spec = importlib.util.spec_from_loader("st", loader); st = importlib.util.module_from_spec(spec); loader.exec_module(st)
anna, parent = pwd.getpwnam("anna"), pwd.getpwnam("parent")
now = int(time.time())
st.record(anna, now - 3000, now)  # 50 minutes used
class Bus:
    terminated = []
    value = {anna.pw_uid: [("3", True)], parent.pw_uid: [("2", True)]}
    def sessions(self): return self.value
    def terminate(self, uid): self.terminated.append(uid)
bus = Bus(); service = st.ScreenTime(bus)
print("r1", service.round()[anna.pw_uid]["stage"])
time.sleep(2)
service.round()
st.record(anna, now - 3420, now - 3000)  # 57 minutes: 3 left
print("r3", service.round()[anna.pw_uid]["stage"])
path = "/run/sloth-os/family/anna.json"
print("mode", oct(os.stat(path).st_mode & 0o777), "group", os.stat(path).st_gid == anna.pw_gid)
st.record(anna, now - 3700, now - 3420)  # over the hour
print("r4", service.round()[anna.pw_uid]["stage"], bus.terminated)
st.GRACE = 0
service.round()
print("r5", bus.terminated)
bus.value = {}
service.round()
print("gone", os.path.exists(path))
EOF
)
echo "$out" | sed 's/^/    /'
[[ $out == *"r1 10"* ]] && ok "50 of 60 minutes used: the 10-minute warning" || bad "no 10-minute warning"
[[ $out == *"r3 5"* ]] && ok "57 minutes: the 5-minute warning" || bad "no 5-minute warning"
[[ $out == *"mode 0o640 group True"* ]] && ok "the state file is readable only by the child" || bad "state file rights"
[[ $out == *"r4 up []"* ]] && ok "time's up: a minute to save first" || bad "time's up"
[[ $out == *"r5 [$(id -u anna)]"* ]] && ok "then signed out (only the child)" || bad "not signed out"
[[ $out == *"gone False"* ]] && ok "signed out: the state file goes" || bad "state file left"
crit=$(grep -c CRITICAL /tmp/timerd.log)
[[ $crit == 0 ]] && ok "malcontent-timerd logged no errors" || bad "malcontent-timerd: $crit CRITICAL lines"

echo "== Off again, and the account removed"
expect "limits off" '"ok": true' family '{"daily": 0, "start": null, "end": null}' child-limits anna
expect "malcontent says no limits" "not enabled" malcontent-client get-session-limits anna
expect "child-remove" '"ok": true' family '' child-remove anna
expect "the account is gone" "no such user" id anna
[[ ! -d /home/anna ]] && ok "its files are gone" || bad "/home/anna is left"
[[ -d /home/parent ]] && ok "the parent's account stays" || bad "the parent's home is gone"

echo
echo "$pass OK, $fail ERROR"
[[ $fail == 0 ]]
