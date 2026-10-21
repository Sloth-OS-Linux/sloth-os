#!/usr/bin/bash
# The unpacked container storage of the Sloth OS image to install, for the ISO.
#   payload.sh <image name> <skopeo source: docker://…, oci:…, or containers-storage:[overlay@/outer/storage+…]…>
# It runs in a throwaway container started from the live image (podman run --rm --privileged); the storage goes into
# a folder mounted from outside (/var/lib/containers/storage), which is mounted at the same place of the live
# system when the ISO is made (tools/build-iso.sh). So no podman commit is needed, and the
# unpacked files (the whiteouts too) go into the ISO unchanged.
set -euxo pipefail

IMAGE="$1"
COPY_FROM="$2"

auth=()
[[ -s /run/secrets/registry-auth ]] && auth=(--authfile /run/secrets/registry-auth)
mkdir -p /var/tmp
# The signature is checked by policy.json when downloading; the local storage does not store signatures
skopeo copy "${auth[@]}" --retry-times 3 --remove-signatures "${COPY_FROM}" "containers-storage:${IMAGE}"
skopeo inspect "containers-storage:${IMAGE}" > /dev/null
