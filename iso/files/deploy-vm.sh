#!/bin/bash
# Csak VM-teszthez (nem kerül a repóba): a javított telepítő-fájlok az élő rendszerbe
set -e
B=http://10.0.2.100:8000
I=/usr/lib/sloth-os/sloth-installer/sloth_installer
for f in system.py controller.py qml/Main.qml; do sudo curl -fsS -o $I/$f $B$I/$f; done
sudo curl -fsS -o /usr/libexec/sloth-os/sloth-install-helper $B/usr/libexec/sloth-os/sloth-install-helper
sudo chmod 755 /usr/libexec/sloth-os/sloth-install-helper
echo DEPLOY-OK
