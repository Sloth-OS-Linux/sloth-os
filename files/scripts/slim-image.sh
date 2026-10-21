#!/usr/bin/env bash
# Slimming the image: only what the system needs to work or to troubleshoot stays
# (decision: 2026-10-15, docs/ROADMAP.md, phase 3). Whatever is removed can be installed from Discover.
# The user apps (Firefox, KDE welcome…) are in remove-default-apps.sh.
# The troubleshooting tools stay too: log viewer, Filelight, nano, vim, htop, nvtop, tmux, remote help (KRdp/krfb).
set -euo pipefail

# --- Csomagok ------------------------------------------------------------------------------------
# kate: KWrite stays · khelpcenter: help center
# just: for the ujust recipes (together with ublue-os-just), we do not use it · toolbox: distrobox stays
# buildah, cosign: developer tools (signature verification works through policy.json, not the cosign command)
# ibus: fcitx5 stays (the recommended one in KDE on Wayland; the Chinese/Japanese/Korean input methods work with it too)
# plasma-workspace-wallpapers: KDE's wallpapers (only Sloth OS's own pictures stay)
# pipewire-config-raop: adds the network's AirPlay speakers (e.g. all MacBooks of a school) as sound
#   outputs. On a Wi-Fi change and with unresponsive devices these disappear and reappear every few seconds,
#   and every new output lifts Plasma's "mute everything" state (2026-10-20, the test's
#   log). Nothing depends on it; whoever wants to send sound to AirPlay can put it back from Discover
REMOVE=(kate khelpcenter just toolbox buildah cosign ibus plasma-workspace-wallpapers pipewire-config-raop)

present=()
for pkg in "${REMOVE[@]}"; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    present+=("$pkg")
  fi
done
if (( ${#present[@]} )); then
  echo "Removing: ${present[*]}"
  dnf -y remove "${present[@]}"
fi

# --- KDE Connect (connecting a phone): included, but off by default ----------------------
# It is not on Flathub, so it is an RPM. It only runs for those who turn it on in Welcome or in Sloth Center
# (/usr/libexec/sloth-os/phone-link); until then it does not start and does not announce itself on the network.
# Besides starting by itself, D-Bus activation is set aside too: otherwise the taskbar's KDE Connect applet
# would start it at login. Turning it on gives both back in the user's own folder.
# The Start menu entries are hidden until it is turned on (turning it on shows them in the user's own folder).
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

# --- Wallpapers ---------------------------------------------------------------------------------
# The own pictures of Plasma and the Fedora packages (Next, F44) cannot be removed as packages (Plasma depends
# on them), so only the files are removed. The old names (Default, Fedora, Next) point to Sloth OS's
# default picture, so whatever still refers to them does not get a black background.
# It still does not show twice in the picture chooser: the picture's ID (metadata.json) is the same.
DEFAULT=SlothOS-metallic-sloth-over-silver-waves
cd /usr/share/wallpapers
[[ -d $DEFAULT ]]
for entry in *; do
  [[ $entry == SlothOS-* ]] || rm -rf "$entry"
done
for name in Default Fedora Next; do
  ln -s "$DEFAULT" "$name"
done
# /usr/share/backgrounds (about 15 MB) stays: the login screen's Fedora defaults may refer to it

# --- BlueBuild leftovers ----------------------------------------------------------------------------
# The default-flatpaks module uses nushell at startup, so nu stays; its plugins
# (polars, query, examples…) are not needed.
rm -f /usr/libexec/bluebuild/nu/nu_plugin_*
