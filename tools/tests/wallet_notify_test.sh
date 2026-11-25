#!/usr/bin/bash
# Run: podman run --rm -v "$PWD":/repo:ro ghcr.io/sloth-os-linux/sloth-os:<tag> bash /repo/tools/tests/wallet_notify_test.sh
# The saved passwords notification with the real KDE password store (kwalletd6 over a real session bus), in the
# Sloth OS image. notify-send is replaced by a recorder that answers "quiet" (Don't remind me).
useradd -m anna 2>/dev/null
mkdir -p /etc/sloth-os
echo '{"users": {"anna": {"topics": [], "sudo": false, "autologin": true}}}' > /etc/sloth-os/admin-policy.json
mkdir -p /tmp/fakebin
cat > /tmp/fakebin/notify-send <<'EOF'
#!/usr/bin/bash
printf '%s\n' "$@" > /tmp/notify-args
echo quiet
EOF
chmod 755 /tmp/fakebin/notify-send
cat > /tmp/run.sh <<'EOF'
export QT_QPA_PLATFORM=offscreen PYTHONPATH=/repo/files/system/usr/lib/sloth-os/sloth-center:/repo/files/system/usr/lib/sloth-os/common
export SLOTH_WALLET_SETTLE=0 PATH=/tmp/fakebin:$PATH XDG_RUNTIME_DIR=/tmp/rt-anna
mkdir -p -m 700 $XDG_RUNTIME_DIR
# what kwalletd6 needs when the bus starts it (no screen here)
dbus-update-activation-environment QT_QPA_PLATFORM XDG_RUNTIME_DIR HOME
kwalletd6 >/tmp/kwalletd.log 2>&1 </dev/null &
KW=$!
sleep 3
echo "kwalletd6 running: $(kill -0 $KW 2>/dev/null && echo yes || echo no)"; tail -3 /tmp/kwalletd.log
check() { python3 -c "from sloth_center import wallet_notify as w; print('$1 ->', repr(w.locked_wallet()))"; }
echo "== the real answers"
for m in isEnabled localWallet wallets; do printf '%s: ' $m; timeout 15 busctl --user call org.kde.kwalletd6 /modules/kwalletd6 org.kde.KWallet $m; done
printf 'isOpen kdewallet: '; timeout 15 busctl --user call org.kde.kwalletd6 /modules/kwalletd6 org.kde.KWallet isOpen s kdewallet
check "no wallet yet"
timeout 30 python3 -m sloth_center.wallet_notify; [ -e /tmp/notify-args ] && echo "BAD: notified without a wallet" || echo "OK: silent without a wallet"
echo "== a wallet exists, locked (as after an automatic sign-in)"
mkdir -p ~/.local/share/kwalletd && printf 'KWALLET\n\r\0\r\n\0\1\2\1' > ~/.local/share/kwalletd/kdewallet.kwl
kill $KW; pkill -x ksecretd; sleep 1; kwalletd6 >/tmp/kwalletd.log 2>&1 </dev/null & KW=$!; sleep 3
printf 'wallets: '; timeout 15 busctl --user call org.kde.kwalletd6 /modules/kwalletd6 org.kde.KWallet wallets
check "locked wallet"
timeout 30 python3 -m sloth_center.wallet_notify
echo "notification:"; sed 's/^/    /' /tmp/notify-args
[ -e ~/.local/state/sloth-os/wallet-notify-off ] && echo "OK: Don't remind me remembered" || echo "BAD: not remembered"
rm -f /tmp/notify-args
timeout 30 python3 -m sloth_center.wallet_notify; [ -e /tmp/notify-args ] && echo "BAD: asked again" || echo "OK: not again after Don't remind me"
echo "== the store turned off"
rm -f ~/.local/state/sloth-os/wallet-notify-off
mkdir -p ~/.config && printf '[Wallet]\nEnabled=false\n' > ~/.config/kwalletrc
timeout 15 busctl --user call org.kde.kwalletd6 /modules/kwalletd6 org.kde.KWallet reconfigure >/dev/null 2>&1
check "store off"
kill $KW 2>/dev/null
EOF
chmod 755 /tmp/run.sh
timeout 150 su anna -c "cd /tmp && dbus-run-session -- bash /tmp/run.sh" >/tmp/out.log 2>&1
echo "exit: $?"
grep -vE "portal|fuse|^\s*$|kf\.|qt\.|QStandardPaths|dbus-daemon" /tmp/out.log
