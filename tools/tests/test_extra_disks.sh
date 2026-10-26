#!/bin/bash
# The installer's "other disks" on real (loop) disks, in a privileged Fedora container (developer test):
#   wsl -d podman-machine-default -u root -- podman run --rm --privileged --cgroups=disabled \
#       -v /mnt/c/Users/batho/sloth-os:/repo:ro registry.fedoraproject.org/fedora:44 bash /repo/tools/tests/test_extra_disks.sh
# One disk is erased (encrypted, with a key file), one keeps its ext4 file system; then configure writes the
# mounts into a fake ostree deployment, and the result is checked (also that the disks really open and mount).
set -euo pipefail
dnf -y -q install btrfs-progs cryptsetup e2fsprogs util-linux python3 >/dev/null 2>&1
work=$(mktemp -d)
truncate -s 400M "$work/erase.img" "$work/keep.img" "$work/root.img"
erase=$(losetup -P --find --show "$work/erase.img")
keep=$(losetup -P --find --show "$work/keep.img")
root=$(losetup --find --show "$work/root.img")
cleanup() {
    umount -R "$work/mnt" 2>/dev/null || true
    for m in /dev/mapper/sloth-test-*; do [ -e "$m" ] && cryptsetup close "$m"; done
    losetup -d "$erase" "$keep" "$root" 2>/dev/null || true
}
trap cleanup EXIT
# the "keep" disk: a partition table with an ext4 file system that has a file on it
printf 'label: gpt\ntype=0fc63daf-8483-4772-8e79-3d69d8477de4\n' | sfdisk -q "$keep"
partx -u "$keep"; udevadm settle 2>/dev/null || true
mkfs.ext4 -q -L "Old Games" "${keep}p1"
mkdir -p "$work/mnt" && mount "${keep}p1" "$work/mnt" && echo keepme > "$work/mnt/file.txt" && umount "$work/mnt"
# the system: a btrfs with an ostree-like deployment
mkfs.btrfs -q "$root"
mount "$root" "$work/mnt"
mkdir -p "$work/mnt/ostree/deploy/default/deploy/abc.0/etc"
umount "$work/mnt"

cat > "$work/run.py" <<EOF
import importlib.machinery, importlib.util, json, sys
loader = importlib.machinery.SourceFileLoader("h", "/repo/iso/files/usr/libexec/sloth-os/sloth-install-helper")
spec = importlib.util.spec_from_loader(loader.name, loader); h = importlib.util.module_from_spec(spec)
loader.exec_module(h)
h.LOG = __import__("pathlib").Path("$work/install.log")
h.whole_disk = lambda path: path in ("$erase", "$keep")   # loop disks are not "disk" in lsblk
extras = h.parse_extra(["erase:$erase", "keep:$keep"], "$root")
extra = h.prepare_extra_disks(extras, True, "Játékok és programok")
print(json.dumps({k: v for k, v in extra.items() if k != "keys"}, indent=1))
account = {"username": "anna", "fullname": "Anna", "password_hash": "\$6\$x"}
h.configure("$root", "hu_HU.UTF-8", ["hu"], [""], "Europe/Budapest", account, extra=extra, display="HDMI-A-1")
EOF
python3 -I "$work/run.py" || { cat "$work/install.log"; exit 1; }

mount "$root" "$work/mnt"
etc="$work/mnt/ostree/deploy/default/deploy/abc.0/etc"
echo "--- fstab"; cat "$etc/fstab"
echo "--- crypttab"; cat "$etc/crypttab"
echo "--- first-user.json"; cat "$etc/sloth-os/first-user.json"; echo
key=$(ls "$etc"/sloth-os/keys/)
stat -c "%a %n" "$etc/sloth-os/keys" "$etc/sloth-os/keys/$key"
test -d "$work/mnt/ostree/deploy/default/var/mnt/data"
test -d "$work/mnt/ostree/deploy/default/var/mnt/old-games"
grep -q "/var/mnt/data btrfs defaults,nofail" "$etc/fstab"
grep -q "/var/mnt/old-games ext4 defaults,nofail" "$etc/fstab"
grep -q '"disks": \["/var/mnt/data"\]' "$etc/sloth-os/first-user.json"
grep -q '"primary": "HDMI-A-1"' "$etc/sloth-os/display.json"
# the erased disk opens with the key file and has the chosen name; the kept one still has its file
cryptsetup open --key-file "$etc/sloth-os/keys/$key" "${erase}p1" sloth-test-erase
test "$(blkid -o value -s LABEL /dev/mapper/sloth-test-erase)" = "Játékok és programok"
test "$(blkid -o value -s TYPE /dev/mapper/sloth-test-erase)" = "btrfs"
mkdir -p "$work/k" && mount "${keep}p1" "$work/k" && test "$(cat "$work/k/file.txt")" = keepme && umount "$work/k"
umount "$work/mnt"
echo "ALL GOOD"
