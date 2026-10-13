#!/usr/bin/env bash
# A Sloth OS boot animáció beállítása alapértelmezettnek.
# Az initramfs újragenerálását a recipe végén lévő `initramfs` modul végzi.
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

echo "Plymouth téma:"
grep -A3 '^\[Daemon\]' /etc/plymouth/plymouthd.conf
