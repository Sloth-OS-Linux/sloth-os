#!/usr/bin/env bash
# A Windows-programok (.exe, .msi), a Linuxos csomagok (AppImage, .deb, .rpm) és a Mac-es fájlok
# alapértelmezett megnyitója a Sloth .exe kezelő legyen (a Mac-eseknél érthető üzenetet ad).
# A meglévő beállításokat megtartjuk, csak ezeket a típusokat írjuk felül.
set -euo pipefail

python3 - <<'PYEOF'
import configparser
target = "/etc/xdg/mimeapps.list"
cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
cp.optionxform = str
cp.read(target, encoding="utf-8")
if not cp.has_section("Default Applications"):
    cp.add_section("Default Applications")
for mime in ("application/x-ms-dos-executable", "application/x-msdownload", "application/x-msi",
             "application/x-ms-installer", "application/vnd.microsoft.portable-executable",
             "application/x-dosexec", "application/vnd.appimage", "application/x-iso9660-appimage",
             "application/vnd.debian.binary-package", "application/x-deb", "application/x-rpm",
             "application/x-redhat-package-manager", "application/x-apple-diskimage", "application/x-xar"):
    cp.set("Default Applications", mime, "org.slothos.exe.desktop;")
with open(target, "w", encoding="utf-8") as f:
    cp.write(f, space_around_delimiters=False)
PYEOF

update-desktop-database /usr/share/applications 2>/dev/null || true
echo "Windows-programok, Linuxos csomagok és Mac-es fájlok megnyitója: org.slothos.exe.desktop"
