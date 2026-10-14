#!/usr/bin/bash
# A Sloth OS élő rendszerének összerakása (az iso/Containerfile futtatja).
# A Titanoboa példáit (examples/zirconium) követi, Anaconda nélkül: a telepítést
# a saját Sloth OS telepítőnk végzi (iso/files/usr/lib/sloth-os/sloth-installer).
set -euxo pipefail


# --- Élő rendszer: initramfs a pendrive-ról induláshoz, automatikus belépés ----------

dnf install -y dracut-live livesys-scripts grub2-efi-x64-cdboot
kernel=$(kernel-install list --json pretty | jq -r '.[] | select(.has_kernel == true) | .version')
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

# Kernel nélküli modulmappák (pl. az alap image-ből maradt üres kmod-mappa) initramfs-e
# összezavarná a Titanoboát, ami a /usr/lib/modules/*/initramfs.img mintát másolja
for dir in /usr/lib/modules/*/; do
    [[ -e "$dir/vmlinuz" ]] || rm -fv "$dir/initramfs.img"
done
[[ $(ls /usr/lib/modules/*/initramfs.img | wc -l) -eq 1 ]]

sed -i "s/^livesys_session=.*/livesys_session=kde/" /etc/sysconfig/livesys
# A livesys az Anaconda miatt a locale1-et követteti a KWinnel. Mi nem használjuk az Anacondát, a
# telepítő a ~/.config/kxkbrc-be írja a választott kiosztást; a locale1 követése ezt késve felülírta.
grep -q "FollowLocale1=true" /usr/libexec/livesys/sessions.d/livesys-kde
sed -i "s/FollowLocale1=true/FollowLocale1=false/" /usr/libexec/livesys/sessions.d/livesys-kde
systemctl enable livesys.service livesys-late.service

# --- A telepítő és az élő rendszer saját fájljai ----------------------------------------

cp -a /src/files/. /
chmod 0755 /usr/bin/sloth-installer /usr/libexec/sloth-os/sloth-install-helper

# --- A telepítendő Sloth OS image ----------------------------------------------------------
# Nem itt kerül bele, és a Firefox sem: a build alatt a kicsomagolt fájlok tulajdonosát nem
# lehet beállítani. A build második lépése teszi bele (iso/payload.sh, privilegizált konténerben,
# podman commit).

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
    sloth-boot-ok.service sloth-steam-proton-default.service \
    rpm-ostreed-automatic.timer bootloader-update.service rpm-ostree-countme.timer \
    $(systemctl list-unit-files --no-legend | awk '{print $1}' | grep -Ei 'flatpak' | grep -Evi 'flatpak-(system|session)-helper' || true); do
    systemctl disable "$unit" 2>/dev/null || true
done
for unit in sloth-steam-vulkan-layers.timer sloth-github-bundle-update.timer sloth-windows-prepare.timer \
    $(systemctl --global list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -Ei 'flatpak' || true); do
    systemctl --global disable "$unit" 2>/dev/null || true
done

dnf clean all
