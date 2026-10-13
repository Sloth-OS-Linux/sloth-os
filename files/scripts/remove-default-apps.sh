#!/usr/bin/env bash
# Kiveszi az alap image-ben lévő felhasználói appokat (RPM), hogy a felhasználó maga
# válasszon a Sloth Üdvözlőben. Csak azt veszi ki, ami tényleg telepítve van.
set -euo pipefail

REMOVE=(firefox firefox-langpacks)

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
