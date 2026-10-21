#!/usr/bin/env bash
# Sets Sloth OS's default appearance for every new user:
# - the SlothSilverDark color scheme (the colors are also written into /etc/xdg/kdeglobals,
#   because KDE apps read them from there, not just from the scheme's name)
# - the Sloth OS logo in os-release (System information, Kickoff etc.)
# The user can switch any time in System Settings; this is only the default.
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
    cp.optionxform = str  # KDE keys are case-sensitive
    cp.read(path, encoding="utf-8")
    return cp

scheme, glob = load(scheme_file), load(target)
for section in scheme.sections():
    # [General] Name is the scheme's name, it is not needed in kdeglobals
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

# The Sloth OS global theme (Windows-like taskbar, splash screen) as the default.
# The taskbar layout is only created for a new user (look-and-feel/.../layouts).
python3 - "$KDEGLOBALS" <<'PYEOF'
import configparser, sys
target = sys.argv[1]
cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
cp.optionxform = str
cp.read(target, encoding="utf-8")
if not cp.has_section("KDE"):
    cp.add_section("KDE")
cp.set("KDE", "LookAndFeelPackage", "org.slothos.desktop")
with open(target, "w", encoding="utf-8") as f:
    cp.write(f, space_around_delimiters=False)
PYEOF
printf '[KSplash]\nEngine=KSplashQML\nTheme=org.slothos.desktop\n' > /etc/xdg/ksplashrc

echo "Default color scheme: ${SCHEME}, global theme: org.slothos.desktop"
grep -A1 '^\[General\]' "$KDEGLOBALS"

# The logo in os-release (icon name: /usr/share/icons/hicolor/scalable/apps/sloth-os.svg)
OS_RELEASE=/usr/lib/os-release
if grep -q '^LOGO=' "$OS_RELEASE"; then
  sed -i 's|^LOGO=.*|LOGO="sloth-os"|' "$OS_RELEASE"
else
  echo 'LOGO="sloth-os"' >> "$OS_RELEASE"
fi

gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
