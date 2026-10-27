#!/usr/bin/env bash
# The Sloth .exe handler should be the default opener of Windows programs (.exe, .msi), Linux packages
# (AppImage, .deb, .rpm), Mac files (for Mac files it gives a clear message) and disc images (.iso).
# The existing settings are kept, only these types are overwritten.
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
             "application/x-redhat-package-manager", "application/x-apple-diskimage", "application/x-xar",
             # disc images: mounted, and the installer on them offered
             "application/x-cd-image", "application/x-iso9660-image"):
    cp.set("Default Applications", mime, "org.slothos.exe.desktop;")
with open(target, "w", encoding="utf-8") as f:
    cp.write(f, space_around_delimiters=False)
PYEOF

update-desktop-database /usr/share/applications 2>/dev/null || true
echo "Opener of Windows programs, Linux packages and Mac files: org.slothos.exe.desktop"
