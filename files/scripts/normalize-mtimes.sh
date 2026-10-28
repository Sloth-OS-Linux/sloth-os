#!/usr/bin/env bash
# The same content must give the same layers (chunkah), so an update downloads only what really changed.
# Files from this repository get the time of the git checkout and generated files the time of the build, so the
# layers holding them (our own files, the wallpapers among the big files, the initramfs) were new in every build:
# ~1 GB per update with nothing changed (2026-10-28). Those files get one fixed modification time here.
# Only the files changed in the last days: a package's files keep the time from the package (the same in every
# build), and changing the time of every file made the container copy all of them (6 GB, minutes).
# It changes nothing on an installed system: ostree does not keep modification times anyway.
# Runs twice: before the initramfs module (dracut --reproducible takes the times of the files it packs) and last.
set -euo pipefail

EPOCH=1767225600  # 2026-01-01 00:00 UTC; earlier than any build, so chunkah keeps it (it only clamps newer times)

count=$(find /usr /etc -xdev -newermt "-3 days" -print -exec touch --no-dereference --date="@${EPOCH}" {} + | wc -l)
echo "Modification time set to $(date -u -d "@${EPOCH}" +%F) on ${count} recently changed files under /usr and /etc"
