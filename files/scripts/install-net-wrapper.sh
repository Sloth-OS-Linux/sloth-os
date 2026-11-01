#!/usr/bin/env bash
# Install Dolphin's Samba usershare shim after the files module copies the system tree.
# Fedora's /usr/local is a symlink into /var, so placing it in files/system makes cp fail.
set -euo pipefail
install -D -m 0755 /usr/libexec/sloth-os/dolphin-net /usr/local/bin/net
