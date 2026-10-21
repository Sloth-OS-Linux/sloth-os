#!/usr/bin/bash
# Assembles the Sloth OS live system (run by iso/Containerfile).
# It follows Titanoboa's examples (examples/zirconium), without Anaconda: installing is done
# by our own Sloth OS installer (iso/files/usr/lib/sloth-os/sloth-installer).
set -euxo pipefail


# --- Live system: an initramfs for booting from the USB stick, automatic login ----------

dnf install -y dracut-live livesys-scripts grub2-efi-x64-cdboot
kernel=$(kernel-install list --json pretty | jq -r '.[] | select(.has_kernel == true) | .version')
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

# An initramfs for module folders without a kernel (e.g. an empty kmod folder left over from the base image)
# would confuse Titanoboa, which copies the /usr/lib/modules/*/initramfs.img pattern
for dir in /usr/lib/modules/*/; do
    [[ -e "$dir/vmlinuz" ]] || rm -fv "$dir/initramfs.img"
done
[[ $(ls /usr/lib/modules/*/initramfs.img | wc -l) -eq 1 ]]

sed -i "s/^livesys_session=.*/livesys_session=kde/" /etc/sysconfig/livesys
# Because of Anaconda, livesys makes KWin follow locale1. We do not use Anaconda; the
# installer writes the chosen layout into ~/.config/kxkbrc, and following locale1 overwrote it with a delay.
grep -q "FollowLocale1=true" /usr/libexec/livesys/sessions.d/livesys-kde
sed -i "s/FollowLocale1=true/FollowLocale1=false/" /usr/libexec/livesys/sessions.d/livesys-kde
systemctl enable livesys.service livesys-late.service

# For installing next to Windows: shrinking the Windows partition (ntfsresize); only needed in the live system
dnf install -y ntfsprogs
command -v ntfsresize ntfscat cryptsetup

# --- The installer's and the live system's own files ----------------------------------------

cp -a /src/files/. /
chmod 0755 /usr/bin/sloth-installer /usr/libexec/sloth-os/sloth-install-helper

# --- A browser for trying it out: Falkon -------------------------------------------------------
# Only in the live system (in the installed system the user chooses one in Welcome).
# Its engine (QtWebEngine) is already in the image, so it is only a few MB.
dnf install -y falkon
sed -i 's|"applications:org.kde.dolphin.desktop",|"applications:org.kde.falkon.desktop",\n    "applications:org.kde.dolphin.desktop",|' \
    /usr/share/plasma/look-and-feel/org.slothos.desktop/contents/layouts/org.kde.plasma.desktop-layout.js
grep -q org.kde.falkon /usr/share/plasma/look-and-feel/org.slothos.desktop/contents/layouts/org.kde.plasma.desktop-layout.js

# --- The Sloth OS image to install ----------------------------------------------------------
# It does not get in here: when the ISO is made, its unpacked container storage goes here
# (iso/payload.sh, tools/build-iso.sh). Unpacked, its files are mostly identical to the live system's
# files, so the ISO's compressor (mksquashfs) stores them only once.
# The installer installs from here: bootc install --source-imgref containers-storage:...
mkdir -p /var/lib/containers/storage /usr/share/sloth-os/installer
cat > /usr/share/sloth-os/installer/image.conf <<EOF
SOURCE_IMGREF=containers-storage:${SLOTH_IMAGE:?}
TARGET_IMGREF=${SLOTH_IMAGE}
EOF

# --- Parts needed for the ISO (Titanoboa / Container-native ISO contract) -----------------

# The boot loader's EFI files under /boot/efi
mkdir -p /boot/efi
cp -av /usr/lib/efi/*/*/EFI /boot/efi/
cp -v /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/fbx64.efi

mkdir -p /usr/lib/bootc-image-builder
cp /src/iso.yaml /usr/lib/bootc-image-builder/iso.yaml

# The live system's root is in RAM; /tmp is small, installing needs a bigger /var/tmp
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

# --- What the installed system needs but is unnecessary or disturbing in the live system ----------

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
