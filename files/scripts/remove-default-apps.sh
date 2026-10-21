#!/usr/bin/env bash
# Removes the user apps (RPMs) in the base image, so the user chooses for themselves
# in Sloth Welcome. It only removes what is really installed.
# KDE's own welcome (plasma-welcome) goes too: Sloth Welcome runs instead, and in the live
# system it covered the installer. It could not be turned off with kded6rc, kded loaded it anyway.
# KDE's first-start wizard (plasma-setup) goes too: the account is asked by the Sloth OS installer,
# and created on first boot by the sloth-first-user service; Sloth Welcome asks the rest.
set -euo pipefail

REMOVE=(firefox firefox-langpacks plasma-welcome plasma-setup)

present=()
for pkg in "${REMOVE[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    present+=("$pkg")
  fi
done

if (( ${#present[@]} )); then
  echo "Removing: ${present[*]}"
  dnf -y remove "${present[@]}"
else
  echo "No app to remove."
fi
