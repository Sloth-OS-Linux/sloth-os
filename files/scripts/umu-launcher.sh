#!/usr/bin/env bash
# umu-launcher: a Windows-programok futtatója a háttérben (a Sloth .exe kezelő használja).
# Nincs a Fedora repóban, ezért a hivatalos GitHub kiadás RPM-jét telepítjük,
# rögzített verzióval és SHA256 ellenőrzéssel.
# Frissítéskor: VERSION és a SHA256 értékek cseréje
#   https://github.com/Open-Wine-Components/umu-launcher/releases
set -euo pipefail

VERSION=1.4.4
declare -A SHA256=(
  [43]=d023fca16dba1b810d574ae7c1c82d0fbd89ae74b93d57c09bcffe41408374bb
  [44]=f38dfe05c109a0ebeaecacad2ebe2e60fddc1fb2e50f7755023553ad256f8b32
)

FEDORA="${OS_VERSION:-$(rpm -E %fedora)}"
if [[ -z "${SHA256[$FEDORA]:-}" ]]; then
  echo "HIBA: nincs umu-launcher ${VERSION} csomag a Fedora ${FEDORA}-hoz; frissítsd a scriptet." >&2
  exit 1
fi

RPM="umu-launcher-${VERSION}.fc${FEDORA}.x86_64.rpm"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

curl -fsSL --retry 3 -o "$TMP/$RPM" \
  "https://github.com/Open-Wine-Components/umu-launcher/releases/download/${VERSION}/${RPM}"
echo "${SHA256[$FEDORA]}  $TMP/$RPM" | sha256sum -c -

dnf -y install "$TMP/$RPM"
umu-run --version || true
