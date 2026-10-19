#!/usr/bin/bash
# A telepítendő Sloth OS image kicsomagolt konténertárolója az ISO-hoz.
#   payload.sh <image neve> <skopeo forrás: docker://…, oci:…, vagy containers-storage:[overlay@/outer/storage+…]…>
# Az élő image-ből indított, eldobható konténerben fut (podman run --rm --privileged); a tároló egy
# kívülről becsatolt mappába kerül (/var/lib/containers/storage), amit az ISO készítésekor az élő
# rendszer ugyanezen helyére csatolunk (tools/build-iso.sh). Így nem kell podman commit, és a
# kicsomagolt fájlok (a törlés-jelölések is) változatlanul kerülnek az ISO-ba.
set -euxo pipefail

IMAGE="$1"
COPY_FROM="$2"

auth=()
[[ -s /run/secrets/registry-auth ]] && auth=(--authfile /run/secrets/registry-auth)
mkdir -p /var/tmp
# Az aláírást a letöltéskor a policy.json ellenőrzi; a helyi tároló aláírást nem tárol
skopeo copy "${auth[@]}" --retry-times 3 --remove-signatures "${COPY_FROM}" "containers-storage:${IMAGE}"
skopeo inspect "containers-storage:${IMAGE}" > /dev/null
