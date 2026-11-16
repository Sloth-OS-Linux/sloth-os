#!/usr/bin/env bash
# The sign-in screen lists the sessions by name only (its session chooser at the bottom): Plasma's own is "Plasma",
# which says little next to TV mode. Its Name lines are replaced with "🖥️ Sloth OS desktop" in 50 languages
# (/usr/share/sloth-os/sessions/plasma-names.desktop, written by tools/gen_desktop_entries.py; TV mode's own entry
# has "🎮 Sloth OS TV mode"). Everything else in the file stays KDE's (Exec, DesktopNames…), and its name
# (plasma.desktop) too: automatic sign-in asks for it by that name (sloth-helper, Session=plasma.desktop).
set -euo pipefail

SESSION=/usr/share/wayland-sessions/plasma.desktop
NAMES=/usr/share/sloth-os/sessions/plasma-names.desktop

[ -f "$SESSION" ] || { echo "session-names: $SESSION is missing" >&2; exit 1; }
grep -q '^Exec=' "$SESSION" || { echo "session-names: $SESSION has no Exec line" >&2; exit 1; }

tmp="$(mktemp)"
# [Desktop Entry] first, then our names, then KDE's lines without its names (Name=, Name[xx]=)
{
    echo "[Desktop Entry]"
    grep '^Name' "$NAMES"
    grep -v -e '^Name=' -e '^Name\[' -e '^\[Desktop Entry\]' "$SESSION"
} > "$tmp"
install -m 0644 "$tmp" "$SESSION"
rm -f "$tmp"

echo "Session names:"
grep -E '^(Name|Name\[hu\]|Exec|DesktopNames)=' "$SESSION"
