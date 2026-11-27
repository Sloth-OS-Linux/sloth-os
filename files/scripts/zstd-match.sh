#!/usr/bin/env bash
# The zstd program at its library's version. The 32-bit graphics drivers (gaming.yml, mesa ...i686) bring the
# 32-bit libzstd, which takes the 64-bit one to the newest version with it; the zstd program stays the base image's.
# A newer library than the program stops it ("incorrect library version"), and dracut (the initramfs step)
# compresses with it: the 2026-11-27 build failed so when libzstd 1.6.0 came out. Same version, no problem.
set -euo pipefail

if ! rpm -q zstd >/dev/null 2>&1; then
  echo "zstd is not installed: nothing to do."
  exit 0
fi
lib=$(rpm -q --qf '%{VERSION}-%{RELEASE}' libzstd.x86_64)
tool=$(rpm -q --qf '%{VERSION}-%{RELEASE}' zstd)
if [[ $lib == "$tool" ]]; then
  echo "zstd and libzstd are both $lib."
  exit 0
fi
echo "zstd $tool, libzstd $lib: the program follows the library."
dnf -y install "zstd-$lib"
tool=$(rpm -q --qf '%{VERSION}-%{RELEASE}' zstd)
if [[ $lib != "$tool" ]]; then
  echo "zstd is still $tool (libzstd $lib)" >&2
  exit 1
fi
zstd --version
