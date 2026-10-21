#!/usr/bin/env bash
# umu-launcher: the runner of Windows programs in the background (used by the Sloth .exe handler).
# It is not in the Fedora repositories, so we install the RPM of the official GitHub release,
# with a pinned version and an SHA256 check.
# When updating: change VERSION and the SHA256 values
#   https://github.com/Open-Wine-Components/umu-launcher/releases
set -euo pipefail

VERSION=1.4.4
declare -A SHA256=(
  [43]=d023fca16dba1b810d574ae7c1c82d0fbd89ae74b93d57c09bcffe41408374bb
  [44]=f38dfe05c109a0ebeaecacad2ebe2e60fddc1fb2e50f7755023553ad256f8b32
)

FEDORA="${OS_VERSION:-$(rpm -E %fedora)}"
if [[ -z "${SHA256[$FEDORA]:-}" ]]; then
  echo "ERROR: no umu-launcher ${VERSION} package for Fedora ${FEDORA}; update the script." >&2
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

# The umu database for recognizing programs (sloth_exe/identify.py). This is only the initial copy:
# after login sloth-windows-prepare updates it. If it is not reachable now, the build goes on
# (recognition then works with the Steam store, and with the database after the first update).
mkdir -p /usr/share/sloth-os
if curl -fsSL --retry 3 -o /usr/share/sloth-os/umu-database.csv \
    https://raw.githubusercontent.com/Open-Wine-Components/umu-database/main/umu-database.csv; then
  head -1 /usr/share/sloth-os/umu-database.csv | grep -q '^TITLE,' || rm -f /usr/share/sloth-os/umu-database.csv
fi
