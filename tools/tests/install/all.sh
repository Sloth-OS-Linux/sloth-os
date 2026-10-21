#!/usr/bin/bash
# A négy eset egymás után, a podman gépen (root). A telepítendő image az ISO-építés tárolójából jön (nincs másolat);
# minden eset után a lemezfájl törlődik, és az fstrim visszaadja a helyet a Windowsnak (ritkított VHD).
mkdir -p /var/tmp/sloth-insttest/work
for s in ${@:-full full-enc win win-enc}; do
  podman --root /var/tmp/sloth-iso-build/storage --runroot /var/tmp/sloth-iso-build/run --cgroup-manager=cgroupfs \
    run --rm --privileged --cgroups=disabled --security-opt label=disable \
    -v /dev:/dev \
    -v /var/tmp/sloth-iso-build/storage:/var/lib/containers/storage \
    -v /var/tmp/sloth-insttest/work:/work \
    -v /mnt/c/Users/batho/sloth-os/iso/files/usr/libexec/sloth-os/sloth-install-helper:/usr/libexec/sloth-os/sloth-install-helper:ro \
    -v /mnt/c/Users/batho/sloth-os/tools/tests/install/run.sh:/run.sh:ro \
    --entrypoint bash localhost/sloth-os-live:latest /run.sh $s
  rm -f /var/tmp/sloth-insttest/work/disk-*.img
  fstrim / >/dev/null 2>&1
done
