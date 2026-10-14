#!/usr/bin/env bash
# Kiveszi az alap image-ben lévő felhasználói appokat (RPM), hogy a felhasználó maga
# válasszon a Sloth Üdvözlőben. Csak azt veszi ki, ami tényleg telepítve van.
# A KDE saját üdvözlője (plasma-welcome) is kikerül: helyette a Sloth Üdvözlő fut, és az élő
# rendszerben a telepítőt takarta el. A kded6rc-vel nem lehetett kikapcsolni, a kded mégis betöltötte.
# A KDE első indítási varázslója (plasma-setup) is kikerül: a fiókot a Sloth OS telepítője kérdezi meg,
# és első induláskor a sloth-first-user szolgáltatás hozza létre; a többit a Sloth Üdvözlő kérdezi.
set -euo pipefail

REMOVE=(firefox firefox-langpacks plasma-welcome plasma-setup)

present=()
for pkg in "${REMOVE[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    present+=("$pkg")
  fi
done

if (( ${#present[@]} )); then
  echo "Eltávolítás: ${present[*]}"
  dnf -y remove "${present[@]}"
else
  echo "Nincs eltávolítandó app."
fi
