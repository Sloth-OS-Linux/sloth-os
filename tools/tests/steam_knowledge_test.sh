#!/usr/bin/bash
# Steam games and the shared knowledge, end to end, in the Sloth OS image (tools/tests/steam_knowledge_e2e.py):
#   podman run --rm -v "$PWD":/repo:ro ghcr.io/sloth-os-linux/sloth-os:<tag> bash /repo/tools/tests/steam_knowledge_test.sh
dnf -y -q install nodejs >/dev/null 2>&1 || echo "no node: the service's validate() cannot be run"
useradd -m gamer 2>/dev/null
su gamer -c "cd /tmp && dbus-run-session -- python3 /repo/tools/tests/steam_knowledge_e2e.py" 2>&1 \
    | grep -vE "portal|fuse|dbus-daemon|^\s*$|qt\.|kf\."
