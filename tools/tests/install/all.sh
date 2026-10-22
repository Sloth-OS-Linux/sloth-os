#!/usr/bin/bash
# The four cases one after the other, as root (on the podman machine or on Linux). The image to install comes from the
# ISO build's storage (no copy; SLOTH_BUILD_DIR, as for tools/build-iso.sh); after each case the disk file is deleted, and
# fstrim gives the space back (on WSL to the sparse VHD). Where the disk files go: SLOTH_TEST_DIR (default /var/tmp/sloth-insttest).
BUILD="${SLOTH_BUILD_DIR:-/var/tmp/sloth-iso-build}"
TEST="${SLOTH_TEST_DIR:-/var/tmp/sloth-insttest}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$TEST/work"
cat > "$TEST/storage.conf" <<EOF
[storage]
driver = "overlay"
graphroot = "$BUILD/storage"
runroot = "/run/containers/storage"
EOF
for s in ${@:-full full-enc win win-enc}; do
  podman --root "$BUILD/storage" --runroot "$BUILD/run" --cgroup-manager=cgroupfs \
    run --rm --privileged --cgroups=disabled --security-opt label=disable \
    -v /dev:/dev \
    -v "$BUILD/storage":"$BUILD/storage" \
    -v "$TEST/storage.conf":/run/sloth-storage.conf:ro \
    -e CONTAINERS_STORAGE_CONF=/run/sloth-storage.conf \
    -v "$TEST/work":/work \
    -v "$REPO/iso/files/usr/libexec/sloth-os/sloth-install-helper":/usr/libexec/sloth-os/sloth-install-helper:ro \
    -v "$REPO/tools/tests/install/run.sh":/run.sh:ro \
    --entrypoint bash localhost/sloth-os-live:latest /run.sh $s
  rm -f "$TEST"/work/disk-*.img
  fstrim "$TEST" >/dev/null 2>&1
done
