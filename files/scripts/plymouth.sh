#!/usr/bin/env bash
# Sets the Sloth OS boot animation as the default.
# Regenerating the initramfs is done by the `initramfs` module at the end of the recipe.
set -euo pipefail

THEME=sloth-os
mkdir -p /etc/plymouth
if [[ -f /etc/plymouth/plymouthd.conf ]] && grep -q '^\[Daemon\]' /etc/plymouth/plymouthd.conf; then
  if grep -q '^Theme=' /etc/plymouth/plymouthd.conf; then
    sed -i "s|^Theme=.*|Theme=${THEME}|" /etc/plymouth/plymouthd.conf
  else
    sed -i "/^\[Daemon\]/a Theme=${THEME}" /etc/plymouth/plymouthd.conf
  fi
else
  printf '[Daemon]\nTheme=%s\n' "$THEME" >> /etc/plymouth/plymouthd.conf
fi

echo "Plymouth theme:"
grep -A3 '^\[Daemon\]' /etc/plymouth/plymouthd.conf
