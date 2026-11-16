#!/usr/bin/env -S bash -exo pipefail
# The installer ISO from the live system's image: Titanoboa's build_iso.sh (ublue-os/titanoboa, commit 5c457c3d,
# Apache License 2.0, https://github.com/ublue-os/titanoboa), with Sloth OS's changes:
#   - it starts on computers in legacy (BIOS) mode too, from a DVD and from a USB stick: GRUB's El Torito image for
#     BIOS next to the EFI one, and GRUB's hybrid MBR (as Fedora's own ISOs do, lorax's x86 template);
#     Titanoboa's ISO started with UEFI only (2026-11-15);
#   - the GRUB menu is hidden: Sloth OS starts after the timeout, Esc brings the menu up (iso/iso.yaml).
# Run by .github/workflows/iso.yml and tools/build-iso.sh in a Fedora container, with the live system's image
# mounted on /rootfs and the output folder on /output.

{ export PS4='+( ${BASH_SOURCE}:${LINENO} ): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'; } 2>/dev/null

# grub2-tools and grub2-pc-modules: grub2-mkimage, the BIOS modules and the hybrid MBR
dnf install -y squashfs-tools xorriso yq mtools dosfstools grub2-tools grub2-pc-modules

mkdir -p \
    /work \
    /work/iso-root \
    /work/iso-root/boot/grub2 \
    /work/iso-root/images/pxeboot \
    /work/iso-root/LiveOS
cd /work || exit 1

# Create the squashfs image of the container image
mksquashfs /rootfs /work/iso-root/LiveOS/squashfs.img -all-root -noappend -e sysroot -e ostree -comp zstd -Xcompression-level 19

iso_config_file=/rootfs/usr/lib/bootc-image-builder/iso.yaml
if [[ ! -f $iso_config_file ]]; then
    echo >&2 "ERROR: Missing /usr/lib/bootc-image-builder/iso.yaml file"
    exit 1
fi

iso_label=$(yq '.label' <$iso_config_file)

# Copy initrd and kernel
cp -av /rootfs/usr/lib/modules/*/initramfs.img /work/iso-root/images/pxeboot/initrd.img
cp -av /rootfs/usr/lib/modules/*/vmlinuz /work/iso-root/images/pxeboot/vmlinuz

# GRUB for BIOS: its modules and its El Torito image, from this container's grub2-pc-modules (the same GRUB version
# makes the image and gives the modules it loads). Titanoboa tested the folders with -f here, so it never copied any.
GRUB_PC=/usr/lib/grub/i386-pc
cp -avT "$GRUB_PC" /work/iso-root/boot/grub2/i386-pc
grub2-mkimage -O i386-pc-eltorito -d "$GRUB_PC" -p /boot/grub2 \
    -o /work/iso-root/boot/grub2/i386-pc/eltorito.img \
    biosdisk iso9660 part_gpt part_msdos fat search search_label search_fs_uuid normal configfile linux gzio \
    all_video video_bochs video_cirrus vbe vga echo test

# Copy efi dir
cp -avT /rootfs/boot/efi/EFI /work/EFI

# Generate grub.cfg (the same for UEFI and BIOS: linux and initrd work in both)
{ grub_cfg="$(</dev/stdin)"; } <<EOF
set timeout=$(yq '.grub2.timeout // 10' <$iso_config_file)
set default="$(yq '.grub2.default // 0' <$iso_config_file)"
set timeout_style=hidden

function load_video {
  insmod all_video
}

load_video
set gfxpayload=keep
insmod gzio
insmod part_gpt
insmod chain

search --no-floppy --set=root -l '$iso_label'

EOF
for i in $(yq '.grub2.entries | keys | .[]' <"$iso_config_file"); do
    entry_name=$(yq ".grub2.entries[$i].name" <"$iso_config_file")
    entry_linux=$(yq ".grub2.entries[$i].linux" <"$iso_config_file")
    entry_initrd=$(yq ".grub2.entries[$i].initrd" <"$iso_config_file")
    { grub_cfg+=$'\n'"$(</dev/stdin)"; } <<EOF
menuentry '$entry_name' {
  linux $entry_linux
  initrd $entry_initrd
}
EOF
done

for dir in /work/EFI/* /work/iso-root/boot/grub2; do
    echo "$grub_cfg" >"$dir/grub.cfg"
done

# For some reason, fedora also copies EFI into /boot/EFI (?), probably because of hardcoded prefix in grub/shim
cp -avT /work/EFI /work/iso-root/EFI

# Generate uefi.img
pushd /work || exit 1
truncate -s 100M /work/uefi.img
mkfs.fat -F32 /work/uefi.img
mcopy -v -i /work/uefi.img -s /work/EFI ::
# BIOS (El Torito, and GRUB's hybrid MBR for USB sticks) first, then UEFI, as lorax lays out Fedora's x86 ISOs.
# A plain MBR partition table, no GPT: partition 1 is the ISO (0x83, active), partition 2 the EFI system partition
# (0xef). Old BIOSes (a Sony VAIO PCG-81313M's Insyde BIOS, 2026-11-16) skip a USB stick that has a protective MBR
# (0xee) or no active partition and start Windows; with this layout it starts. UEFI finds the EFI partition in the
# MBR as well.
xorriso -as mkisofs \
    -R \
    -V "$iso_label" \
    --grub2-mbr "$GRUB_PC/boot_hybrid.img" \
    --mbr-force-bootable \
    -partition_offset 16 \
    -append_partition 2 0xef ./uefi.img \
    -iso_mbr_part_type 0x83 \
    -c boot.catalog --boot-catalog-hide \
    -b boot/grub2/i386-pc/eltorito.img -no-emul-boot -boot-load-size 4 -boot-info-table --grub2-boot-info \
    -eltorito-alt-boot \
    -e --interval:appended_partition_2:all:: \
    -no-emul-boot \
    -iso-level 3 \
    -o "/output/$iso_label.iso" \
    iso-root
