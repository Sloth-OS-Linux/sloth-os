#!/usr/bin/bash
# A négy eset egymás után, rootként (a podman gépen vagy Linuxon). A telepítendő image az ISO-építés tárolójából jön
# (nincs másolat; SLOTH_BUILD_DIR, mint a tools/build-iso.sh-nál); minden eset után a lemezfájl törlődik, és az fstrim
# visszaadja a helyet (WSL-en a ritkított VHD-nek). A lemezfájlok helye: SLOTH_TEST_DIR (alapból /var/tmp/sloth-insttest).
BUILD="${SLOTH_BUILD_DIR:-/var/tmp/sloth-iso-build}"
TEST="${SLOTH_TEST_DIR:-/var/tmp/sloth-insttest}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$TEST/work"
for s in ${@:-full full-enc win win-enc}; do
  podman --root "$BUILD/storage" --runroot "$BUILD/run" --cgroup-manager=cgroupfs \
    run --rm --privileged --cgroups=disabled --security-opt label=disable \
    -v /dev:/dev \
    -v "$BUILD/storage":/var/lib/containers/storage \
    -v "$TEST/work":/work \
    -v "$REPO/iso/files/usr/libexec/sloth-os/sloth-install-helper":/usr/libexec/sloth-os/sloth-install-helper:ro \
    -v "$REPO/tools/tests/install/run.sh":/run.sh:ro \
    --entrypoint bash localhost/sloth-os-live:latest /run.sh $s
  rm -f "$TEST"/work/disk-*.img
  fstrim "$TEST" >/dev/null 2>&1
done
