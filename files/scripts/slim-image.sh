#!/usr/bin/env bash
# Az image karcsúsítása: csak az marad, ami a rendszer működéséhez vagy a hibaelhárításhoz kell
# (döntés: 2026-10-15, docs/ROADMAP.md, 3. fázis). Ami kikerül, a Discoverből telepíthető.
# A felhasználói appok (Firefox, KDE üdvözlő…) a remove-default-apps.sh-ban vannak.
# Maradnak a hibaelhárító eszközök is: naplónéző, Filelight, nano, vim, htop, nvtop, tmux, távsegítség (KRdp/krfb).
set -euo pipefail

# --- Csomagok ------------------------------------------------------------------------------------
# kate: a KWrite marad · kde-connect: telefonos app · khelpcenter: súgóközpont
# just: az ujust receptekhez (az ublue-os-just-tal együtt), nem használjuk · toolbox: a distrobox marad
# buildah, cosign: fejlesztői eszközök (az aláírás-ellenőrzés a policy.json-nal megy, nem a cosign paranccsal)
# ibus: a fcitx5 marad (KDE-ben Waylanden az ajánlott, a kínai/japán/koreai beviteli módok vele is megvannak)
# plasma-workspace-wallpapers: a KDE háttérképei (csak a Sloth OS saját képei maradnak)
REMOVE=(kate kde-connect khelpcenter just toolbox buildah cosign ibus plasma-workspace-wallpapers)

present=()
for pkg in "${REMOVE[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    present+=("$pkg")
  fi
done
if (( ${#present[@]} )); then
  echo "Eltávolítás: ${present[*]}"
  dnf -y remove "${present[@]}"
fi

# --- Háttérképek ---------------------------------------------------------------------------------
# A Plasma és a Fedora-csomagok saját képeit (Next, F44) nem lehet csomagként törölni (a Plasma függ
# tőlük), ezért csak a fájlok kerülnek ki. A régi nevek (Default, Fedora, Next) a Sloth OS
# alapértelmezett képére mutatnak, hogy ami még rájuk hivatkozik, ne fekete hátteret kapjon.
# A képválasztóban így sem látszik kétszer: a kép azonosítója (metadata.json) ugyanaz.
DEFAULT=SlothOS-metallic-sloth-over-silver-waves
cd /usr/share/wallpapers
[[ -d $DEFAULT ]]
for entry in *; do
  [[ $entry == SlothOS-* ]] || rm -rf "$entry"
done
for name in Default Fedora Next; do
  ln -s "$DEFAULT" "$name"
done
# A /usr/share/backgrounds (kb. 15 MB) marad: a bejelentkező képernyő Fedora-alapbeállításai hivatkozhatnak rá

# --- BlueBuild maradéka ----------------------------------------------------------------------------
# A nushellt a default-flatpaks modul induláskor használja, ezért a nu marad; a bővítményei
# (polars, query, példák…) nem kellenek.
rm -f /usr/libexec/bluebuild/nu/nu_plugin_*
