#!/usr/bin/env bash
# The NVIDIA variant: the 32-bit NVIDIA libraries for Windows programs (see gaming.yml, mesa ...i686).
# If the base image has the NVIDIA driver but its 32-bit part is missing, we install the version matching the driver.
# Nothing to do on the AMD/Intel variant.
set -euo pipefail

pkg=""
for candidate in nvidia-driver-libs xorg-x11-drv-nvidia-libs; do
  if rpm -q "$candidate.x86_64" >/dev/null 2>&1; then
    pkg=$candidate
    break
  fi
done
if [[ -z $pkg ]]; then
  echo "No NVIDIA driver in the image: nothing to do."
  exit 0
fi
if rpm -q "$pkg.i686" >/dev/null 2>&1; then
  echo "The 32-bit NVIDIA libraries are already there: $(rpm -q "$pkg.i686")"
  exit 0
fi
version="$(rpm -q --qf '%{EPOCH}:%{VERSION}-%{RELEASE}' "$pkg.x86_64" | sed 's/^(none)://')"
echo "32-bit NVIDIA libraries: $pkg-$version.i686"
# The NVIDIA repository may be turned off in the base image: we turn it on only for this install
dnf -y install --setopt=install_weak_deps=False --enablerepo='*nvidia*' "$pkg-$version.i686"
