#!/usr/bin/env bash
# Renames the system to Sloth OS.
# IMPORTANT: ID=fedora stays, because lots of tools (dnf, rpm-ostree, Flatpak, installers)
# rely on it. Only the displayed names are changed.
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

# Sloth OS's own version; VERSION_ID stays Fedora's (Fedora's tools build on it).
# The displayed version shows the base too: "Sloth OS 1.1 (Fedora Atomic 44)". KDE's
# System information shows VERSION (/etc/xdg/kcm-about-distrorc), not VERSION_ID.
SLOTH_VERSION="1.1"
FEDORA_VERSION="$(. "$OS_RELEASE" && echo "$VERSION_ID")"
set_key NAME "Sloth OS"
set_key VERSION "${SLOTH_VERSION} (Fedora Atomic ${FEDORA_VERSION})"
set_key PRETTY_NAME "Sloth OS ${SLOTH_VERSION} (Fedora Atomic ${FEDORA_VERSION})"
set_key VARIANT "Desktop"
set_key VARIANT_ID "sloth-os"
set_key DEFAULT_HOSTNAME "sloth"
# The website; support and bug reports on GitHub
set_key HOME_URL "https://sloth-os-linux.github.io/"
set_key SUPPORT_URL "https://github.com/Sloth-OS-Linux/sloth-os/issues"
set_key BUG_REPORT_URL "https://github.com/Sloth-OS-Linux/sloth-os/issues"

echo "Sloth OS branding done:"
grep -E '^(NAME|VERSION|VERSION_ID|PRETTY_NAME|VARIANT|DEFAULT_HOSTNAME)=' "$OS_RELEASE"
