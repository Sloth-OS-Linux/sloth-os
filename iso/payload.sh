#!/usr/bin/bash
# A telepítendő Sloth OS image és a Firefox beletétele a kész élő image-be (a build második lépése).
#   payload.sh <telepítendő image> <frissítések forrása>
# Privilegizált konténerben fut (podman run --privileged), az eredményt podman commit menti:
# a build alatti (podman build) környezetben a csomagolt fájlok tulajdonosát nem lehet
# beállítani, ezért nem lehet ezt az iso/build.sh-ban megcsinálni. Lásd: tools/build-iso.ps1.
#
# Kicsomagolt konténertárolóba (containers-storage) kerül, nem tömörített OCI-rétegként: így
# a fájljai többnyire azonosak az élő rendszer fájljaival, és az ISO tömörítője (mksquashfs)
# ezeket csak egyszer tárolja. A telepítő innen telepít: bootc install --source-imgref containers-storage:...
set -euxo pipefail

SOURCE_IMAGE="$1"
TARGET_IMAGE="$2"

auth=()
[[ -s /run/secrets/registry-auth ]] && auth=(--authfile /run/secrets/registry-auth)
mkdir -p /var/tmp
# Az aláírást a letöltéskor a policy.json ellenőrzi; a helyi tároló aláírást nem tárol
skopeo copy "${auth[@]}" --retry-times 3 --remove-signatures \
    "docker://${SOURCE_IMAGE}" "containers-storage:${SOURCE_IMAGE}"
skopeo inspect "containers-storage:${SOURCE_IMAGE}" > /dev/null

mkdir -p /usr/share/sloth-os/installer
cat > /usr/share/sloth-os/installer/image.conf <<EOF
SOURCE_IMGREF=containers-storage:${SOURCE_IMAGE}
TARGET_IMGREF=${TARGET_IMAGE}
EOF

# --- Firefox: böngésző a kipróbáláshoz, és tartalék a telepített rendszerbe ----------------
# Csak az élő rendszerben van. Ha telepítéskor nincs internet, a telepítő átmásolja a
# telepített rendszerbe (sloth-install-helper), különben a felhasználó az Üdvözlőben választ.

# a flatpak (bwrap) írni próbálja a /proc/sys-t, ami a build alatt csak olvasható
mount -o remount,rw /proc/sys || true
flatpak remote-add --system --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
# minden nyelv fordítása, hogy a Firefox a választott nyelven szóljon
flatpak config --system --set languages "*"
flatpak install --system --noninteractive flathub org.mozilla.firefox
# a tálcára is kitűzzük (csak az élő rendszerben)
sed -i 's|"applications:org.kde.dolphin.desktop",|"applications:org.mozilla.firefox.desktop",\n    "applications:org.kde.dolphin.desktop",|' \
    /usr/share/plasma/look-and-feel/org.slothos.desktop/contents/layouts/org.kde.plasma.desktop-layout.js
grep -q org.mozilla.firefox /usr/share/plasma/look-and-feel/org.slothos.desktop/contents/layouts/org.kde.plasma.desktop-layout.js
