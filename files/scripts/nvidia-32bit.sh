#!/usr/bin/env bash
# NVIDIA-s változat: a 32 bites NVIDIA-könyvtárak a Windows-programoknak (lásd gaming.yml, mesa ...i686).
# Ha az alap image-ben van NVIDIA-driver, de a 32 bites része hiányzik, a driverrel egyező verziót tesszük fel.
# AMD/Intel változaton nincs teendő.
set -euo pipefail

pkg=""
for candidate in nvidia-driver-libs xorg-x11-drv-nvidia-libs; do
  if rpm -q "$candidate.x86_64" >/dev/null 2>&1; then
    pkg=$candidate
    break
  fi
done
if [[ -z $pkg ]]; then
  echo "Nincs NVIDIA-driver az image-ben: nincs teendő."
  exit 0
fi
if rpm -q "$pkg.i686" >/dev/null 2>&1; then
  echo "A 32 bites NVIDIA-könyvtárak már megvannak: $(rpm -q "$pkg.i686")"
  exit 0
fi
version="$(rpm -q --qf '%{EPOCH}:%{VERSION}-%{RELEASE}' "$pkg.x86_64" | sed 's/^(none)://')"
echo "32 bites NVIDIA-könyvtárak: $pkg-$version.i686"
# Az NVIDIA-tároló az alap image-ben ki lehet kapcsolva: csak erre a telepítésre kapcsoljuk be
dnf -y install --setopt=install_weak_deps=False --enablerepo='*nvidia*' "$pkg-$version.i686"
