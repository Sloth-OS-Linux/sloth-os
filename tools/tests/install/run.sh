#!/usr/bin/bash
# Telepítési teszt konténerben, loop-lemezen: run.sh full|full-enc|win|win-enc
# Az élő rendszer image-ében fut (--privileged, /dev a gazdáé). A telepítő segéd eredeti kódja fut;
# csak a "teljes lemez?" ellenőrzés (loop-eszköz) és a firmware boot-bejegyzés (efibootmgr) van kikapcsolva.
set -uo pipefail
S=$1
W=/work
PASS='Jelszo-12345'
CRYPT='titkos-jelszo-99'
say() { echo "### $*"; }

# UEFI-s gép mímelése (a konténerben nincs /sys/firmware/efi; nélküle a bootupd csak BIOS-os betöltőt tenne fel,
# és a telepítő Windows mellé nem engedne). Üres tmpfs: a valódi firmware-változókhoz semmi nem nyúl.
mount -t tmpfs tmpfs /sys/firmware && mkdir -p /sys/firmware/efi/efivars

# udev (az lsblk partíciószámaihoz és a bootupd-hez)
mkdir -p /run/udev
/usr/lib/systemd/systemd-udevd --daemon >/dev/null 2>&1
udevadm trigger >/dev/null 2>&1; udevadm settle --timeout=30

# a telepítendő image a konténer saját tárolójába (egyszer; a /var/lib/containers/storage tartós mappa)
SRC=$(sed -n 's/^SOURCE_IMGREF=//p' /usr/share/sloth-os/installer/image.conf)
NAME=${SRC#*:}
skopeo inspect "containers-storage:$NAME" >/dev/null 2>&1 || { say "HIBA: nincs meg az image: $NAME"; exit 1; }

IMG=$W/disk-$S.img
rm -f "$IMG"
case $S in win*) truncate -s 100G "$IMG" ;; *) truncate -s 40G "$IMG" ;; esac
LOOP=$(losetup --find --show --partscan "$IMG")
trap 'umount -R /run/sloth-install/target 2>/dev/null; umount /tmp/m/w 2>/dev/null; cryptsetup close sloth-root 2>/dev/null; losetup -d $LOOP; rm -f $IMG' EXIT
say "lemez: $LOOP ($S)"

if [[ $S == win* ]]; then
    # „Windowsos” lemez: EFI (bootmgfw.efi), MSR, NTFS adatokkal
    printf 'label: gpt\nsize=100MiB, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="EFI system partition"\nsize=16MiB, type=E3C9E316-0B5C-4DB8-817D-F92DF00215AE, name="Microsoft reserved partition"\ntype=EBD0A0A2-B9E5-4433-87C0-68B6B72699C7, name="Basic data partition"\n' | sfdisk -q "$LOOP"
    partx -u "$LOOP" 2>/dev/null; udevadm settle --timeout=30
    mkfs.fat -F 32 -n SYSTEM "${LOOP}p1" >/dev/null
    mkdir -p /tmp/m/w && mount "${LOOP}p1" /tmp/m/w && mkdir -p /tmp/m/w/EFI/Microsoft/Boot && echo windows-loader > /tmp/m/w/EFI/Microsoft/Boot/bootmgfw.efi && umount /tmp/m/w
    mkfs.ntfs -Q -q -L Windows "${LOOP}p3" || { say "HIBA: mkfs.ntfs"; exit 1; }
    ntfs-3g "${LOOP}p3" /tmp/m/w && mkdir -p /tmp/m/w/Users/anna && head -c 50M /dev/urandom > /tmp/m/w/Users/anna/adat.bin && sha256sum /tmp/m/w/Users/anna/adat.bin | cut -d' ' -f1 > $W/win-sum && umount /tmp/m/w
    WINESP_UUID=$(blkid -o value -s UUID "${LOOP}p1")
    udevadm settle --timeout=30
fi

ARGS=(install --disk "$LOOP" --locale hu_HU.UTF-8 --keyboard hu --timezone Europe/Budapest --username teszt --fullname "Teszt Elek")
INPUT="$PASS"
[[ $S == *enc ]] && { ARGS+=(--encrypt); INPUT="$PASS
$CRYPT"; }
[[ $S == win* ]] && ARGS+=(--beside-windows --size-gib 45)

say "telepítés: ${ARGS[*]}"
START=$(date +%s)
cat > /tmp/wrap.py <<'PY'
import importlib.machinery, importlib.util, sys
l = importlib.machinery.SourceFileLoader("h", "/usr/libexec/sloth-os/sloth-install-helper")
spec = importlib.util.spec_from_loader("h", l); h = importlib.util.module_from_spec(spec); l.exec_module(h)
h.whole_disk = lambda path: True           # loop-eszköz
h.rename_boot_entry = lambda *a: None      # a gazdagép firmware-éhez ne nyúljon
sys.argv = ["sloth-install-helper"] + sys.argv[1:]
sys.exit(h.main())
PY
printf '%s\n' "$INPUT" | python3 -I /tmp/wrap.py "${ARGS[@]}" > $W/out-$S.txt 2>&1
RC=$?
cp /tmp/sloth-install.log $W/log-$S.txt 2>/dev/null
say "kilépési kód: $RC, $(( $(date +%s) - START )) mp; utolsó üzenet: $(grep -v '^$' $W/out-$S.txt | tail -1)"
[[ $RC == 0 ]] || { tail -15 /tmp/sloth-install.log; exit 1; }

# --- Ellenőrzés -------------------------------------------------------------------------
ok=0; bad=0
check() { if eval "$2"; then ok=$((ok+1)); echo "  rendben: $1"; else bad=$((bad+1)); echo "  HIBA:    $1"; fi; }
partx -u "$LOOP" 2>/dev/null; udevadm settle --timeout=30
sfdisk -d "$LOOP" | grep '^/dev' | sed 's/^/  /'
DUMP=$(sfdisk -d "$LOOP")
OWN_ESP=$(sfdisk -d "$LOOP" | grep -i 'C12A7328' | grep -v 'EFI system partition' | tail -1 | cut -d' ' -f1)
[[ $S == win* ]] || OWN_ESP=${LOOP}p2
mkdir -p /tmp/m/e && mount -o ro "$OWN_ESP" /tmp/m/e
check "rendszerbetöltő a saját EFI-partíción (shimx64.efi)" "[ -f /tmp/m/e/EFI/fedora/shimx64.efi ]"
check "boot menü állapota (sloth-boot.env)" "[ -f /tmp/m/e/EFI/fedora/sloth-boot.env ]"
if [[ $S == win* ]]; then
    check "Windows-bejegyzés a boot menüben" "grep -q $WINESP_UUID /tmp/m/e/EFI/fedora/sloth-windows.cfg"
    check "a menü látható (Windows mellett)" "grep -q 'sloth_show_menu=1' /tmp/m/e/EFI/fedora/sloth-boot.env"
fi
umount /tmp/m/e
if [[ $S == win* ]]; then
    check "a Windows EFI-partíció típusa visszaállt" "sfdisk --part-type $LOOP 1 | grep -qi C12A7328"
    mount -o ro "${LOOP}p1" /tmp/m/e
    check "a Windows EFI-partíción nincs Fedora/Sloth" "[ ! -e /tmp/m/e/EFI/fedora ]"
    check "a Windows indítója megvan" "[ -f /tmp/m/e/EFI/Microsoft/Boot/bootmgfw.efi ]"
    umount /tmp/m/e
    check "NTFS ép (ntfsfix -n)" "ntfsfix -n ${LOOP}p3 >/dev/null 2>&1"
    ntfs-3g -o ro "${LOOP}p3" /tmp/m/w
    check "a Windows-fájl változatlan" "[ \"\$(sha256sum /tmp/m/w/Users/anna/adat.bin | cut -d' ' -f1)\" = \"\$(cat $W/win-sum)\" ]"
    umount /tmp/m/w
fi
ROOT=$(sfdisk -d "$LOOP" | grep -i '4F68BCE3' | cut -d' ' -f1)
check "rendszerpartíció (Linux root típus) megvan" "[ -n '$ROOT' ]"
check "a munkapartíció törölve" "! sfdisk -d $LOOP | grep -q sloth-install-tmp"
if [[ $S == *enc ]]; then
    check "LUKS2 a rendszerpartíción" "cryptsetup luksDump $ROOT | grep -q 'Version:.*2'"
    check "kinyitható a jelszóval" "printf '%s' '$CRYPT' | cryptsetup open --key-file=- $ROOT sloth-check"
    DEV=/dev/mapper/sloth-check
else
    DEV=$ROOT
fi
mkdir -p /tmp/m/r && mount -o ro,subvolid=5 "$DEV" /tmp/m/r
check "btrfs, „Sloth OS” címkével" "[ \"\$(blkid -o value -s LABEL $DEV)\" = 'Sloth OS' ]"
DEPLOY=$(ls -d /tmp/m/r/ostree/deploy/*/deploy/*.0 /tmp/m/r/*/ostree/deploy/*/deploy/*.0 2>/dev/null | head -1)
check "ostree deployment megvan" "[ -n '$DEPLOY' ]"
check "a fiók adatai (első induláskor jön létre)" "grep -q '\"teszt\"' $DEPLOY/etc/sloth-os/first-user.json"
check "magyar billentyűzet" "grep -q 'XkbLayout\" \"hu' $DEPLOY/etc/X11/xorg.conf.d/00-keyboard.conf"
check "magyar nyelv" "grep -q 'hu_HU.UTF-8' $DEPLOY/etc/locale.conf"
check "időzóna" "readlink $DEPLOY/etc/localtime | grep -q Budapest"
if [[ $S == *enc ]]; then
    check "crypttab" "grep -q '^luks-' $DEPLOY/etc/crypttab"
    BOOTDEV=$(sfdisk -d "$LOOP" | grep 'name="boot"' | cut -d' ' -f1)
    mkdir -p /tmp/m/b && mount -o ro "$BOOTDEV" /tmp/m/b
    check "rd.luks.uuid a rendszerindítás paraméterei között" "grep -q 'rd.luks.uuid=luks-' /tmp/m/b/loader/entries/*.conf"
    umount /tmp/m/b
fi
[[ $S == win* ]] && check "Windows mellett helyi idő (adjtime LOCAL)" "grep -q LOCAL $DEPLOY/etc/adjtime"
SIZE=$(lsblk -bno SIZE --nodeps "$ROOT")
echo "  rendszerpartíció mérete: $((SIZE / 1024**3)) GiB"
umount /tmp/m/r
[[ $S == *enc ]] && cryptsetup close sloth-check
say "EREDMÉNY $S: $ok rendben, $bad hiba"
[[ $bad == 0 ]]
