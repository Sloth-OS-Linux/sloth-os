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

# A Sloth OS saját verziója; a VERSION_ID marad a Fedoráé (a Fedora eszközei arra építenek).
# A megjelenített verzióban az alap is látszik: „Sloth OS 1.0 (Fedora Atomic 44)”. A KDE
# Rendszerinformáció a VERSION-t mutatja (/etc/xdg/kcm-about-distrorc), nem a VERSION_ID-t.
SLOTH_VERSION="1.0"
FEDORA_VERSION="$(. "$OS_RELEASE" && echo "$VERSION_ID")"
set_key NAME "Sloth OS"
set_key VERSION "${SLOTH_VERSION} (Fedora Atomic ${FEDORA_VERSION})"
set_key PRETTY_NAME "Sloth OS ${SLOTH_VERSION} (Fedora Atomic ${FEDORA_VERSION})"
set_key VARIANT "Desktop"
set_key VARIANT_ID "sloth-os"
set_key DEFAULT_HOSTNAME "sloth"
# TODO: ha lesz saját weboldal, a HOME_URL-t átírni.
set_key HOME_URL "https://github.com/Sloth-OS-Linux/sloth-os"
set_key SUPPORT_URL "https://github.com/Sloth-OS-Linux/sloth-os/issues"
set_key BUG_REPORT_URL "https://github.com/Sloth-OS-Linux/sloth-os/issues"

echo "Sloth OS branding kész:"
grep -E '^(NAME|VERSION|VERSION_ID|PRETTY_NAME|VARIANT|DEFAULT_HOSTNAME)=' "$OS_RELEASE"
