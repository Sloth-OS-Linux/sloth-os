#!/usr/bin/env bash
# Dolphin's KAuth helper invokes `net` from a restricted system PATH, which can
# bypass /usr/local/bin. Preserve Samba's real binary and put the shim at its
# canonical path so both Dolphin and Sloth Center use it.
set -euo pipefail
if [[ ! -e /usr/libexec/sloth-os/net.real ]]; then
  install -D -m 0755 /usr/bin/net /usr/libexec/sloth-os/net.real
fi
ln -sfn /usr/libexec/sloth-os/dolphin-net /usr/bin/net
