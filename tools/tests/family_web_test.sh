#!/usr/bin/bash
# The parental controls' web filter (/usr/libexec/sloth-os/family-web) with real dnsmasq and nftables, in a Fedora 44
# container with its own network (the repository under /repo; it needs the internet):
#   podman run --rm --cap-add NET_ADMIN,NET_RAW -v "$PWD":/repo:ro registry.fedoraproject.org/fedora:44 \
#       bash /repo/tools/tests/family_web_test.sh
# There is no systemd: systemd-resolved's stub (127.0.0.53) is played by an unfiltered dnsmasq, and the family name
# server is started with sloth-family-dns.service's own arguments. A child (anna) and a parent ask the same names.
set -uo pipefail
dnf -q -y install dnsmasq nftables bind-utils curl shadow-utils util-linux python3 >/dev/null 2>&1 \
    || { echo "dnf failed"; exit 1; }
useradd -m -u 1001 anna && useradd -m -u 1000 parent
dnsmasq --conf-file=/dev/null --pid-file= --listen-address=127.0.0.53 --bind-interfaces --no-resolv \
    --server=1.1.1.1 --user=root || { echo "stub failed"; exit 1; }
echo "nameserver 127.0.0.53" > /etc/resolv.conf
args=$(sed -n '/^ExecStart=/,/^Restart=/p' /repo/files/system/usr/lib/systemd/system/sloth-family-dns.service \
    | grep -v '^Restart=' | sed 's/^ExecStart=//; s/\\$//' | tr '\n' ' ' \
    | sed 's#/usr/sbin/dnsmasq --keep-in-foreground##; s/--user=dnsmasq --group=dnsmasq/--user=root/')
eval dnsmasq "$args" || { echo "family name server failed"; exit 1; }
echo '{"users": ["anna", "parent"]}' > /tmp/web.json
groupadd -f wheel && usermod -aG wheel parent   # a parent on the list is never filtered
SLOTH_FAMILY_WEB=/tmp/web.json python3 -I /repo/files/system/usr/libexec/sloth-os/family-web --print | nft -f - \
    || { echo "nft failed"; exit 1; }

ok=0; bad=0
check() { if eval "$2"; then ok=$((ok+1)); echo "  ok:    $1"; else bad=$((bad+1)); echo "  WRONG: $1"; fi; }
ask() { runuser -u "$1" -- dig +short +time=4 +tries=2 "${@:2}" | grep -E '^[0-9.]+$' | head -1; }
http() { runuser -u "$1" -- curl -s -m 8 -o /dev/null -w "%{http_code}" "${@:2}"; }

check "a parent reaches an adult site's name" '[ -n "$(ask parent pornhub.com)" ]'
check "a child doesn't" '[ -z "$(ask anna pornhub.com)" ]'
check "a child's Google is SafeSearch (forcesafesearch.google.com)" '[ "$(ask anna www.google.com)" = 216.239.38.120 ]'
check "a child's YouTube is restricted (restrict.youtube.com)" '[ "$(ask anna www.youtube.com)" = 216.239.38.119 ]'
check "a parent's Google is the normal one" '[ "$(ask parent www.google.com)" != 216.239.38.120 ]'
check "ordinary names work for a child" '[ -n "$(ask anna example.com)" ]'
check "Firefox's canary says 'no such name' to a child" '[ -z "$(ask anna use-application-dns.net)" ]'
check "a child asking 8.8.8.8 itself is filtered too" '[ -z "$(ask anna @8.8.8.8 pornhub.com)" ]'
check "and over TCP" '[ -z "$(ask anna +tcp pornhub.com)" ]'
check "DNS over HTTPS is closed for a child" '[ "$(http anna "https://1.1.1.1/dns-query?name=a.com" -H accept:application/dns-json)" = 000 ]'
check "and open for a parent" '[ "$(http parent "https://1.1.1.1/dns-query?name=a.com" -H accept:application/dns-json)" = 200 ]'
check "DNS over TLS is closed for a child" '! runuser -u anna -- curl -s -m 5 telnet://1.1.1.1:853 </dev/null'
check "a child opens an ordinary website" '[ "$(http anna https://example.com)" = 200 ]'
echo "$ok ok, $bad wrong"
[ "$bad" = 0 ]
