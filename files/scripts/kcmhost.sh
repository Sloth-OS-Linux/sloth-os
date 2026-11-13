#!/usr/bin/env bash
# One settings app: KDE's settings pages inside Sloth Center (Sloth Center → More settings).
# 1. Builds org.slothos.kcmhost (files/system/usr/src/sloth-os/kcmhost), the small QML module that loads a KDE
#    settings page into Sloth Center's window, against this image's own Qt and KDE Frameworks. The build tools are
#    removed again and so is the source.
# 2. Only if that worked: `systemsettings` opens Sloth Center (the real one stays at /usr/libexec/sloth-os/
#    systemsettings.real, the wrapper falls back to it) and System Settings' own menu entry is hidden.
set -euo pipefail

SRC=/usr/src/sloth-os/kcmhost
DEST=/usr/lib64/qt6/qml/org/slothos/kcmhost
BUILD=/tmp/kcmhost-build

before=$(rpm -qa --qf '%{NAME}\n' | sort -u)
dnf -y install --setopt=install_weak_deps=False \
  cmake gcc-c++ make extra-cmake-modules kf6-kcmutils-devel kf6-kcoreaddons-devel qt6-qtbase-devel \
  qt6-qtdeclarative-devel
after=$(rpm -qa --qf '%{NAME}\n' | sort -u)
added=$(comm -13 <(echo "$before") <(echo "$after"))

cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j"$(nproc)"
install -d "$DEST"
install -m 0755 "$BUILD/qml/org/slothos/kcmhost/libkcmhost.so" "$DEST/"
install -m 0644 "$BUILD/qml/org/slothos/kcmhost/qmldir" "$BUILD/qml/org/slothos/kcmhost/kcmhost.qmltypes" "$DEST/"

if [[ -n "$added" ]]; then
  # shellcheck disable=SC2086
  dnf -y remove $added
fi
rm -rf "$BUILD" /usr/src/sloth-os
rmdir /usr/src 2>/dev/null || true

# The module must load with the Qt that Sloth Center (PySide6) uses (the same Fedora Qt). If it does not, the
# build stops here, so a broken settings app never reaches anyone (Sloth Center would still open KDE's pages in
# their own window, but this should be noticed and fixed).
if ! QT_QPA_PLATFORM=offscreen python3 - <<'EOF'
import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
app = QGuiApplication(sys.argv[:1])
engine = QQmlEngine()
c = QQmlComponent(engine)
c.setData(b"import QtQuick\nimport org.slothos.kcmhost\nItem { property int n: KcmCatalog.modules().length }",
          QUrl("file:///check.qml"))
o = c.create()
if o is None or o.property("n") < 20:
    print("kcmhost check failed:", c.errorString(), file=sys.stderr)
    sys.exit(1)
print("kcmhost: %d settings pages" % o.property("n"))
EOF
then
  echo "kcmhost: the module does not load with PySide6's Qt" >&2
  exit 1
fi

# --- systemsettings → Sloth Center ---------------------------------------------------------------------
if [[ ! -e /usr/libexec/sloth-os/systemsettings.real ]]; then
  install -D -m 0755 /usr/bin/systemsettings /usr/libexec/sloth-os/systemsettings.real
fi
install -m 0755 /usr/libexec/sloth-os/systemsettings-wrapper /usr/bin/systemsettings

# System Settings' own entry leaves the menus and the search (Sloth Center is the settings app); the file stays,
# so anything that starts it by its name still works (and lands in Sloth Center)
desktop=/usr/share/applications/systemsettings.desktop
if [[ -f "$desktop" ]] && ! grep -q '^NoDisplay=true' "$desktop"; then
  sed -i '/^\[Desktop Entry\]/a NoDisplay=true' "$desktop"
fi
