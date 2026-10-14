#!/usr/bin/bash
# A Sloth OS élő rendszerének összerakása (az iso/Containerfile futtatja).
#   build.sh <telepítendő image> <frissítések forrása>
# A Titanoboa példáit (examples/zirconium) követi, Anaconda nélkül: a telepítést
# a saját Sloth OS telepítőnk végzi (iso/files/usr/lib/sloth-os/sloth-installer).
set -euxo pipefail

SOURCE_IMAGE="$1"   # amit az ISO-ba csomagolunk és feltelepítünk
TARGET_IMAGE="$2"   # ahonnan a telepített rendszer a frissítéseit kapja
PAYLOAD=/usr/share/sloth-os/installer/image

# --- Élő rendszer: initramfs a pendrive-ról induláshoz, automatikus belépés ----------

dnf install -y dracut-live livesys-scripts grub2-efi-x64-cdboot
kernel=$(kernel-install list --json pretty | jq -r '.[] | select(.has_kernel == true) | .version')
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

sed -i "s/^livesys_session=.*/livesys_session=kde/" /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service

# --- A telepítő és az élő rendszer saját fájljai ----------------------------------------

cp -a /src/files/. /
chmod 0755 /usr/bin/sloth-installer /usr/libexec/sloth-os/sloth-install-helper

# --- A telepítendő Sloth OS image, internet nélküli telepítéshez -------------------------
# OCI-könyvtárként (tömörített rétegek); a telepítő a bootc install --source-imgref oci:...
# kapcsolóval innen telepít, konténer futtatása nélkül.

auth=()
[[ -s /run/secrets/registry-auth ]] && auth=(--authfile /run/secrets/registry-auth)
mkdir -p "$(dirname "$PAYLOAD")"
# Az aláírást a letöltéskor a policy.json ellenőrzi; az OCI-könyvtár aláírást nem tud tárolni
skopeo copy "${auth[@]}" --retry-times 3 --remove-signatures "docker://${SOURCE_IMAGE}" "oci:${PAYLOAD}:latest"
cat > /usr/share/sloth-os/installer/image.conf <<EOF
SOURCE_IMGREF=oci:${PAYLOAD}:latest
TARGET_IMGREF=${TARGET_IMAGE}
EOF

# --- ISO-hoz szükséges részek (Titanoboa / Container-native ISO contract) -----------------

# A rendszerindító EFI fájljai a /boot/efi alatt
mkdir -p /boot/efi
cp -av /usr/lib/efi/*/*/EFI /boot/efi/
cp -v /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/fbx64.efi

mkdir -p /usr/lib/bootc-image-builder
cp /src/iso.yaml /usr/lib/bootc-image-builder/iso.yaml

# Az élő rendszer gyökere RAM-ban van; a /tmp kicsi, a telepítéshez nagyobb /var/tmp kell
rm -rf /var/tmp
mkdir -p /var/tmp
cat > /etc/systemd/system/var-tmp.mount <<'EOF'
[Unit]
Description=Larger tmpfs for /var/tmp on the live system

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=50%%,nr_inodes=1m

[Install]
WantedBy=local-fs.target
EOF
systemctl enable var-tmp.mount

rm -f /etc/localtime
systemd-firstboot --timezone UTC

# --- Ami a telepített rendszerbe kell, de az élő rendszeren felesleges vagy zavaró ----------

for unit in \
    sloth-hide-boot-menu.service sloth-steam-proton-default.service \
    rpm-ostreed-automatic.timer bootloader-update.service rpm-ostree-countme.timer \
    $(systemctl list-unit-files --no-legend | awk '{print $1}' | grep -Ei 'flatpak' | grep -Evi 'flatpak-(system|session)-helper' || true); do
    systemctl disable "$unit" 2>/dev/null || true
done
for unit in sloth-steam-vulkan-layers.timer sloth-github-bundle-update.timer \
    $(systemctl --global list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -Ei 'flatpak' || true); do
    systemctl --global disable "$unit" 2>/dev/null || true
done

dnf clean all
