#!/usr/bin/env bash
# A Windows-programok futtatója gyárilag az image-ben: Proton (UMU-Proton) és a Steam Linux Runtime (sniper).
# Így az első .exe letöltés és internet nélkül, rögtön indul: első használatkor a
# /usr/libexec/sloth-os/windows-runtime-seed a felhasználó mappájába másolja őket, oda, ahol az umu-launcher
# keresi. Az újabb verziókat utána az umu magától tölti le a háttérben (sloth-windows-prepare).
# Rögzített verziók ellenőrzőösszeggel. Frissítéskor: a verziók és az összegek cseréje
#   https://github.com/Open-Wine-Components/umu-proton/releases  (a .sha512sum fájlból)
#   https://repo.steampowered.com/steamrt3/images/latest-public-beta.txt  (a verzió mappájában: SHA256SUMS)
set -euo pipefail

PROTON=UMU-Proton-10.0-4
PROTON_SHA512=5e1e7c99e773b4d0757f90075c5ff7f5282bedd13a694fc0414486122e68c9452d3fb971f32ab32704d4463c9622475a44e58fbd014069aa1e84e27b4a4ed7e5
RUNTIME=3.0.20261007.263965
RUNTIME_SHA256=c0485966093731ec59d3b53fd1639ec454d94a877531e70750d9aa40d2a2f23b

DEST=/usr/share/sloth-os/windows-runtime
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST"

curl -fsSL --retry 3 -o "$TMP/$PROTON.tar.gz" \
  "https://github.com/Open-Wine-Components/umu-proton/releases/download/$PROTON/$PROTON.tar.gz"
echo "$PROTON_SHA512  $TMP/$PROTON.tar.gz" | sha512sum -c -
tar -xzf "$TMP/$PROTON.tar.gz" -C "$DEST"
rm "$TMP/$PROTON.tar.gz"
test -x "$DEST/$PROTON/proton"

curl -fsSL --retry 3 -o "$TMP/SteamLinuxRuntime_sniper.tar.xz" \
  "https://repo.steampowered.com/steamrt3/images/$RUNTIME/SteamLinuxRuntime_sniper.tar.xz"
echo "$RUNTIME_SHA256  $TMP/SteamLinuxRuntime_sniper.tar.xz" | sha256sum -c -
tar -xJf "$TMP/SteamLinuxRuntime_sniper.tar.xz" -C "$TMP"
mv "$TMP/SteamLinuxRuntime_sniper" "$DEST/steamrt3"
test -f "$DEST/steamrt3/VERSIONS.txt"
ls -d "$DEST"/steamrt3/sniper_platform_* >/dev/null

du -sh "$DEST"/*
