#!/usr/bin/bash
# Install test in a container, on a loop disk: run.sh full|full-enc|win|win-enc
# It runs in the live system's image (--privileged, the host's /dev). The installer helper's original code runs;
# only the "whole disk?" check (loop device) and the firmware boot entry (efibootmgr) are switched off.
set -uo pipefail
S=$1
W=/work
PASS='Password-12345'
CRYPT='secret-pass-99'
say() { echo "### $*"; }

# Faking a UEFI machine (the container has no /sys/firmware/efi; without it bootupd would only install a BIOS loader,
# and the installer would not allow next to Windows). An empty tmpfs: the real firmware variables are not touched.
mount -t tmpfs tmpfs /sys/firmware && mkdir -p /sys/firmware/efi/efivars

# udev (for lsblk's partition numbers and for bootupd)
mkdir -p /run/udev
/usr/lib/systemd/systemd-udevd --daemon >/dev/null 2>&1
udevadm trigger >/dev/null 2>&1; udevadm settle --timeout=30

# the image to install, in the container's own storage (once; /var/lib/containers/storage is a persistent folder)
SRC=$(sed -n 's/^SOURCE_IMGREF=//p' /usr/share/sloth-os/installer/image.conf)
NAME=${SRC#*:}
skopeo inspect "containers-storage:$NAME" >/dev/null 2>&1 || { say "ERROR: the image is missing: $NAME"; exit 1; }

IMG=$W/disk-$S.img
rm -f "$IMG"
case $S in win*) truncate -s 100G "$IMG" ;; *) truncate -s 40G "$IMG" ;; esac
LOOP=$(losetup --find --show --partscan "$IMG")
trap 'umount -R /run/sloth-install/target 2>/dev/null; umount /tmp/m/w 2>/dev/null; cryptsetup close sloth-root 2>/dev/null; losetup -d $LOOP; rm -f $IMG' EXIT
say "disk: $LOOP ($S)"

if [[ $S == win* ]]; then
    # A Windows-like disk: EFI (bootmgfw.efi), MSR, NTFS with Windows markers and user data
    printf 'label: gpt\nsize=100MiB, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="EFI system partition"\nsize=16MiB, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, name="Microsoft reserved partition"\ntype=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="Basic data partition"\n' | sfdisk -q "$LOOP"
    partx -u "$LOOP" 2>/dev/null; udevadm settle --timeout=30
    mkfs.fat -F 32 -n SYSTEM "${LOOP}p1" >/dev/null
    mkdir -p /tmp/m/w && mount "${LOOP}p1" /tmp/m/w && mkdir -p /tmp/m/w/EFI/Microsoft/Boot && echo windows-loader > /tmp/m/w/EFI/Microsoft/Boot/bootmgfw.efi && umount /tmp/m/w
    mkfs.ntfs -Q -q -L Windows "${LOOP}p3" || { say "HIBA: mkfs.ntfs"; exit 1; }
    ntfs-3g "${LOOP}p3" /tmp/m/w && mkdir -p /tmp/m/w/Users/anna /tmp/m/w/Windows/System32/config && \
        echo windows-loader > /tmp/m/w/Windows/System32/winload.efi && \
        echo windows-registry > /tmp/m/w/Windows/System32/config/SYSTEM && \
        head -c 50M /dev/urandom > /tmp/m/w/Users/anna/adat.bin && \
        sha256sum /tmp/m/w/Users/anna/adat.bin | cut -d' ' -f1 > $W/win-sum && umount /tmp/m/w
    WINESP_UUID=$(blkid -o value -s UUID "${LOOP}p1")
    udevadm settle --timeout=30
fi

ARGS=(install --disk "$LOOP" --locale hu_HU.UTF-8 --keyboard hu --timezone Europe/Budapest --username tester --fullname "Test User")
INPUT="$PASS"
[[ $S == *enc ]] && { ARGS+=(--encrypt); INPUT="$PASS
$CRYPT"; }
[[ $S == win* ]] && ARGS+=(--beside-windows --size-gib 45)

say "installing: ${ARGS[*]}"
START=$(date +%s)
cat > /tmp/wrap.py <<'PY'
import importlib.machinery, importlib.util, sys
l = importlib.machinery.SourceFileLoader("h", "/usr/libexec/sloth-os/sloth-install-helper")
spec = importlib.util.spec_from_loader("h", l); h = importlib.util.module_from_spec(spec); l.exec_module(h)
h.whole_disk = lambda path: True           # loop device
h.rename_boot_entry = lambda *a: None      # do not touch the host's firmware
sys.argv = ["sloth-install-helper"] + sys.argv[1:]
sys.exit(h.main())
PY
printf '%s\n' "$INPUT" | python3 -I /tmp/wrap.py "${ARGS[@]}" > $W/out-$S.txt 2>&1
RC=$?
cp /tmp/sloth-install.log $W/log-$S.txt 2>/dev/null
say "exit code: $RC, $(( $(date +%s) - START )) s; last message: $(grep -v '^$' $W/out-$S.txt | tail -1)"
[[ $RC == 0 ]] || { tail -15 /tmp/sloth-install.log; exit 1; }

# --- Checks -------------------------------------------------------------------------
ok=0; bad=0
check() { if eval "$2"; then ok=$((ok+1)); echo "  rendben: $1"; else bad=$((bad+1)); echo "  HIBA:    $1"; fi; }
partx -u "$LOOP" 2>/dev/null; udevadm settle --timeout=30
sfdisk -d "$LOOP" | grep '^/dev' | sed 's/^/  /'
DUMP=$(sfdisk -d "$LOOP")
OWN_ESP=$(sfdisk -d "$LOOP" | grep -i 'C12A7328' | grep -v 'EFI system partition' | tail -1 | cut -d' ' -f1)
[[ $S == win* ]] || OWN_ESP=${LOOP}p2
mkdir -p /tmp/m/e && mount -o ro "$OWN_ESP" /tmp/m/e
check "boot loader on its own EFI partition (shimx64.efi)" "[ -f /tmp/m/e/EFI/fedora/shimx64.efi ]"
check "boot menu state (sloth-boot.env)" "[ -f /tmp/m/e/EFI/fedora/sloth-boot.env ]"
if [[ $S == win* ]]; then
    check "Windows entry in the boot menu" "grep -q $WINESP_UUID /tmp/m/e/EFI/fedora/sloth-windows.cfg"
    check "the menu is visible (next to Windows)" "grep -q 'sloth_show_menu=1' /tmp/m/e/EFI/fedora/sloth-boot.env"
fi
umount /tmp/m/e
if [[ $S == win* ]]; then
    check "the Windows EFI partition's type was restored" "sfdisk --part-type $LOOP 1 | grep -qi C12A7328"
    mount -o ro "${LOOP}p1" /tmp/m/e
    check "no Fedora/Sloth on the Windows EFI partition" "[ ! -e /tmp/m/e/EFI/fedora ]"
    check "the Windows boot loader is there" "[ -f /tmp/m/e/EFI/Microsoft/Boot/bootmgfw.efi ]"
    umount /tmp/m/e
    check "NTFS intact (ntfsfix -n)" "ntfsfix -n ${LOOP}p3 >/dev/null 2>&1"
    mkdir -p /tmp/m/w && ntfs-3g -o ro "${LOOP}p3" /tmp/m/w
    check "the Windows file is unchanged" "[ \"\$(sha256sum /tmp/m/w/Users/anna/adat.bin | cut -d' ' -f1)\" = \"\$(cat $W/win-sum)\" ]"
    umount /tmp/m/w
fi
ROOT=$(sfdisk -d "$LOOP" | grep -i '4F68BCE3' | cut -d' ' -f1)
check "system partition (Linux root type) exists" "[ -n '$ROOT' ]"
check "the work partition is deleted" "! sfdisk -d $LOOP | grep -q sloth-install-tmp"
if [[ $S == *enc ]]; then
    check "LUKS2 on the system partition" "cryptsetup luksDump $ROOT | grep -q 'Version:.*2'"
    check "opens with the password" "printf '%s' '$CRYPT' | cryptsetup open --key-file=- $ROOT sloth-check"
    DEV=/dev/mapper/sloth-check
else
    DEV=$ROOT
fi
mkdir -p /tmp/m/r && mount -o ro,subvolid=5 "$DEV" /tmp/m/r
check "btrfs, labelled \"Sloth OS\"" "[ \"\$(blkid -o value -s LABEL $DEV)\" = 'Sloth OS' ]"
DEPLOY=$(ls -d /tmp/m/r/ostree/deploy/*/deploy/*.0 /tmp/m/r/*/ostree/deploy/*/deploy/*.0 2>/dev/null | head -1)
check "ostree deployment megvan" "[ -n '$DEPLOY' ]"
check "the account details (created on first boot)" "grep -q '\"tester\"' $DEPLOY/etc/sloth-os/first-user.json"
check "Hungarian keyboard" "grep -q 'XkbLayout\" \"hu' $DEPLOY/etc/X11/xorg.conf.d/00-keyboard.conf"
check "Hungarian language" "grep -q 'hu_HU.UTF-8' $DEPLOY/etc/locale.conf"
check "time zone" "readlink $DEPLOY/etc/localtime | grep -q Budapest"
if [[ $S == *enc ]]; then
    check "crypttab" "grep -q '^luks-' $DEPLOY/etc/crypttab"
    BOOTDEV=$(sfdisk -d "$LOOP" | grep 'name="boot"' | cut -d' ' -f1)
    mkdir -p /tmp/m/b && mount -o ro "$BOOTDEV" /tmp/m/b
    check "rd.luks.uuid among the boot parameters" "grep -q 'rd.luks.uuid=luks-' /tmp/m/b/loader/entries/*.conf"
    umount /tmp/m/b
fi
[[ $S == win* ]] && check "local time next to Windows (adjtime LOCAL)" "grep -q LOCAL $DEPLOY/etc/adjtime"
SIZE=$(lsblk -bno SIZE --nodeps "$ROOT")
echo "  system partition size: $((SIZE / 1024**3)) GiB"
umount /tmp/m/r
[[ $S == *enc ]] && cryptsetup close sloth-check
say "RESULT $S: $ok OK, $bad errors"
[[ $bad == 0 ]]
