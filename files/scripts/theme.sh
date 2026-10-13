#!/usr/bin/env bash
# Beállítja a Sloth OS alapértelmezett megjelenését minden új felhasználónak:
# - SlothSilverDark színséma (a színeket a /etc/xdg/kdeglobals-ba is beírjuk,
#   mert a KDE appok onnan olvassák, nem csak a séma nevéből)
# - Sloth OS logó az os-release-ben (Rendszerinformáció, Kickoff stb.)
# A felhasználó a Rendszerbeállításokban bármikor átválthat, ez csak az alapérték.
set -euo pipefail

SCHEME=SlothSilverDark
SCHEME_FILE="/usr/share/color-schemes/${SCHEME}.colors"
KDEGLOBALS=/etc/xdg/kdeglobals

mkdir -p "$(dirname "$KDEGLOBALS")"
touch "$KDEGLOBALS"

python3 - "$SCHEME_FILE" "$KDEGLOBALS" <<'EOF'
import configparser, sys
scheme_file, target = sys.argv[1], sys.argv[2]

def load(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    cp.optionxform = str  # a KDE kulcsok kis- és nagybetű-érzékenyek
    cp.read(path, encoding="utf-8")
    return cp

scheme, glob = load(scheme_file), load(target)
for section in scheme.sections():
    # A [General] Name a séma neve, a kdeglobals-ba nem kell
    if section == "General":
        continue
    if not glob.has_section(section):
        glob.add_section(section)
    for key, value in scheme.items(section):
        glob.set(section, key, value)

if not glob.has_section("General"):
    glob.add_section("General")
glob.set("General", "ColorScheme", scheme.get("General", "ColorScheme"))

with open(target, "w", encoding="utf-8") as f:
    glob.write(f, space_around_delimiters=False)
EOF

echo "Alapértelmezett színséma: ${SCHEME}"
grep -A1 '^\[General\]' "$KDEGLOBALS"

# Logó az os-release-ben (ikonnév: /usr/share/icons/hicolor/scalable/apps/sloth-os.svg)
OS_RELEASE=/usr/lib/os-release
if grep -q '^LOGO=' "$OS_RELEASE"; then
  sed -i 's|^LOGO=.*|LOGO="sloth-os"|' "$OS_RELEASE"
else
  echo 'LOGO="sloth-os"' >> "$OS_RELEASE"
fi

gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
