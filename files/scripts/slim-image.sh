#!/usr/bin/env bash
# Az image karcsúsítása: csak az marad, ami a rendszer működéséhez vagy a hibaelhárításhoz kell
# (döntés: 2026-10-15, docs/ROADMAP.md, 3. fázis). Ami kikerül, a Discoverből telepíthető.
# A felhasználói appok (Firefox, KDE üdvözlő…) a remove-default-apps.sh-ban vannak.
# Maradnak a hibaelhárító eszközök is: naplónéző, Filelight, nano, vim, htop, nvtop, tmux, távsegítség (KRdp/krfb).
set -euo pipefail

# --- Csomagok ------------------------------------------------------------------------------------
# kate: a KWrite marad · khelpcenter: súgóközpont
# just: az ujust receptekhez (az ublue-os-just-tal együtt), nem használjuk · toolbox: a distrobox marad
# buildah, cosign: fejlesztői eszközök (az aláírás-ellenőrzés a policy.json-nal megy, nem a cosign paranccsal)
# ibus: a fcitx5 marad (KDE-ben Waylanden az ajánlott, a kínai/japán/koreai beviteli módok vele is megvannak)
# plasma-workspace-wallpapers: a KDE háttérképei (csak a Sloth OS saját képei maradnak)
# pipewire-config-raop: a hálózat AirPlay-hangszóróit (pl. egy iskola összes MacBookját) hangkimenetként
#   veszi fel. Wi-Fi-váltáskor és a nem válaszoló eszközöknél ezek pár másodpercenként eltűnnek és újra
#   megjelennek, és minden új kimenet feloldja a Plasma „mindent némít” állapotát (2026-10-20, a teszt
#   naplója). Semmi nem függ tőle; aki AirPlayre küldené a hangot, a Discoverből visszateheti
REMOVE=(kate khelpcenter just toolbox buildah cosign ibus plasma-workspace-wallpapers pipewire-config-raop)

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

# --- KDE Connect (telefon összekötése): benne van, de alapból ki van kapcsolva ----------------------
# Nincs a Flathubon, ezért RPM. Csak annak fut, aki az Üdvözlőben vagy a Sloth Központban bekapcsolja
# (/usr/libexec/sloth-os/phone-link); addig nem indul el, és nem hirdeti magát a hálózaton.
# A magától indulás mellett a D-Bus-indítást is félretesszük: különben a tálca KDE Connect-kisalkalmazása
# bejelentkezéskor elindítaná. A bekapcsolás a felhasználó saját mappájában adja vissza mindkettőt.
# A Start menü bejegyzései rejtve, amíg nincs bekapcsolva (a bekapcsolás a saját mappában mutatja őket).
KDECONNECT=/usr/share/sloth-os/kdeconnect
mkdir -p "$KDECONNECT"
grep -q '^Exec=' /etc/xdg/autostart/org.kde.kdeconnect.daemon.desktop
cp /etc/xdg/autostart/org.kde.kdeconnect.daemon.desktop "$KDECONNECT/"
sed -i '/^\[Desktop Entry\]/a Hidden=true' /etc/xdg/autostart/org.kde.kdeconnect.daemon.desktop
mv /usr/share/dbus-1/services/org.kde.kdeconnect.service "$KDECONNECT/"
for entry in org.kde.kdeconnect.app org.kde.kdeconnect.sms; do
  f=/usr/share/applications/$entry.desktop
  [[ -f $f ]] || continue
  cp "$f" "$KDECONNECT/"
  sed -i '/^NoDisplay=/d; /^\[Desktop Entry\]/a NoDisplay=true' "$f"
done

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
