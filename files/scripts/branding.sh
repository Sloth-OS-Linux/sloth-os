#!/usr/bin/env bash
# Átnevezi a rendszert Sloth OS-re.
# FONTOS: az ID=fedora marad, mert rengeteg eszköz (dnf, rpm-ostree, Flatpak, telepítő)
# erre támaszkodik. Csak a megjelenített neveket cseréljük.
set -euo pipefail

OS_RELEASE=/usr/lib/os-release

set_key() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$OS_RELEASE"; then
    sed -i "s|^${key}=.*|${key}=\"${value}\"|" "$OS_RELEASE"
  else
    echo "${key}=\"${value}\"" >> "$OS_RELEASE"
  fi
}

set_key NAME "Sloth OS"
set_key PRETTY_NAME "Sloth OS"
set_key VARIANT "Desktop"
set_key VARIANT_ID "sloth-os"
set_key DEFAULT_HOSTNAME "sloth"
# TODO: ha lesz saját weboldal, a HOME_URL-t átírni.
set_key HOME_URL "https://github.com/bathorizsolt/sloth-os"
set_key SUPPORT_URL "https://github.com/bathorizsolt/sloth-os/issues"
set_key BUG_REPORT_URL "https://github.com/bathorizsolt/sloth-os/issues"

echo "Sloth OS branding kész:"
grep -E '^(NAME|PRETTY_NAME|VARIANT|DEFAULT_HOSTNAME)=' "$OS_RELEASE"
