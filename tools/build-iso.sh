#!/usr/bin/bash
# Builds the Sloth OS installer ISO locally, on Linux (rootful Podman).
# Developer tool, not in the image. On Windows: tools/build-iso.ps1, in CI: .github/workflows/iso.yml
#
#   tools/build-iso.sh [image] [output folder]
#
# Start it as a normal user: it signs in to ghcr.io with the GitHub CLI's token (needs the "read:packages" scope,
# once: gh auth refresh -h github.com -s read:packages), then continues as administrator (sudo,
# with a graphical password prompt if SUDO_ASKPASS is set).
#
# Environment variables:
#   SLOTH_BUILD_DIR   work folder and Podman storage (default /var/tmp/sloth-iso-build; about 25–28 GB needed)
#   SLOTH_SQUASH=1    squashes the layers of the image to install into one: replaced / deleted files (e.g. the
#                     old kernel) drop out, the ISO is smaller (estimate: 0.5–1 GB). The price: the installed machine's first
#                     update downloads the whole image (its layers do not match the registry's). For releases.
#   http(s)_proxy     for the downloads; the containers use it too (they run on the host's network)
set -euo pipefail

IMAGE="${1:-ghcr.io/sloth-os-linux/sloth-os:latest}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$(realpath -m "${2:-$REPO/out}")"
WORK="${SLOTH_BUILD_DIR:-/var/tmp/sloth-iso-build}"

# The Titanoboa ISO builder script from a pinned commit (when updating: change the SHA in .github/workflows/iso.yml too)
TITANOBOA_COMMIT="5c457c3d0518bd17e754be0fd98a60d29d26abb4"
LIVE_IMAGE="localhost/sloth-os-live:latest"

# --- 1. As a normal user: credentials, then restart as administrator ------------------
if [[ $EUID -ne 0 ]]; then
    user="$(gh api user --jq .login)" || { echo "The GitHub CLI is not signed in (gh auth login)." >&2; exit 1; }
    auth="$(mktemp)"
    trap 'rm -f "$auth"' EXIT
    printf '{"auths":{"ghcr.io":{"auth":"%s"}}}\n' "$(printf '%s:%s' "$user" "$(gh auth token)" | base64 -w0)" > "$auth"
    sudo_args=(--preserve-env=http_proxy,https_proxy,HTTP_PROXY,HTTPS_PROXY,no_proxy,NO_PROXY,SLOTH_BUILD_DIR,SLOTH_SQUASH)
    [[ -n "${SUDO_ASKPASS:-}" ]] && sudo_args+=(-A)
    sudo "${sudo_args[@]}" SLOTH_REGISTRY_AUTH="$auth" SLOTH_OWNER="$(id -u):$(id -g)" \
        "${BASH_SOURCE[0]}" "$IMAGE" "$OUT_DIR"
    exit
fi

# --- 2. As administrator ------------------------------------------------------------------------
mkdir -p "$WORK" "$OUT_DIR"
AUTH="$WORK/auth.json"
install -m 600 "${SLOTH_REGISTRY_AUTH:?}" "$AUTH"
# The unpacked image to install (about 12 GB) is only needed until the ISO is made
trap 'rm -f "$AUTH"; rm -rf "$WORK/payload-oci" "$WORK/payload"' EXIT

# On the WSL Podman machine (tools/build-iso.ps1) systemd does not manage the containers' cgroups, and there is no
# "pids" controller: cgroupfs is needed there, and the containers start without cgroups (without this the build's first
# RUN step stops with a "Failed to set unit properties" error)
pm_opts=() run_opts=()
if grep -qi microsoft /proc/version; then
    pm_opts=(--cgroup-manager=cgroupfs)
    run_opts=(--cgroups=disabled)
fi
pm() { podman --root "$WORK/storage" --runroot "$WORK/run" "${pm_opts[@]}" "$@"; }

echo "== Downloading the base image: $IMAGE"
pm pull --authfile "$AUTH" "$IMAGE"

echo "== Building the live system: $LIVE_IMAGE"
pm build --pull=never --network host --security-opt label=disable \
    --build-arg BASE_IMAGE="$IMAGE" -t "$LIVE_IMAGE" "$REPO/iso"

# The unpacked container storage of the image to install goes into a separate folder (iso/payload.sh), which is
# mounted in place of the live system's /var/lib/containers/storage when the ISO is made. No podman commit is needed
# (on the slow machine that alone took an hour and a half), and the files go into the ISO unchanged.
# The image to install is not downloaded again, and there is no temporary OCI copy either (that was another ~12 GB): the
# unpacker reads straight from the storage already downloaded (mounted in, as a containers-storage source).
payload_src="$IMAGE"
if [[ "${SLOTH_SQUASH:-0}" == 1 ]]; then
    echo "== Squashing the layers of the image to install"
    mkdir -p "$WORK/squash"
    printf 'FROM %s\n' "$IMAGE" > "$WORK/squash/Containerfile"
    pm build --pull=never --squash-all --network none --security-opt label=disable \
        -t localhost/sloth-os-payload:latest -f "$WORK/squash/Containerfile" "$WORK/squash"
    payload_src="localhost/sloth-os-payload:latest"
fi
echo "== Unpacking the image to install"
rm -rf "$WORK/payload-oci" "$WORK/payload"
mkdir -p "$WORK/payload"
driver="$(pm info --format '{{.Store.GraphDriverName}}')"
pm run --rm "${run_opts[@]}" --privileged --network none \
    -v "$REPO/iso/payload.sh":/payload.sh:ro \
    -v "$WORK/storage":/outer/storage \
    -v "$WORK/payload":/var/lib/containers/storage \
    "$LIVE_IMAGE" bash /payload.sh "$IMAGE" "containers-storage:[$driver@/outer/storage+/run/outer]$payload_src"
[[ "$payload_src" == "$IMAGE" ]] || pm rmi "$payload_src"

echo "== Making the ISO (Titanoboa ${TITANOBOA_COMMIT:0:7})"
curl -fsSL -o "$WORK/build_iso.sh" \
    "https://raw.githubusercontent.com/ublue-os/titanoboa/${TITANOBOA_COMMIT}/build_iso.sh"
# Hidden GRUB menu: by default Sloth OS starts right away, Esc brings the menu up (iso/iso.yaml)
grep -q "set menu_auto_hide=false" "$WORK/build_iso.sh" || { echo "Titanoboa's GRUB template has changed." >&2; exit 1; }
sed -i "s/set menu_auto_hide=false/set timeout_style=hidden/" "$WORK/build_iso.sh"
rm -f "$OUT_DIR"/*.iso
pm run --rm "${run_opts[@]}" --network host --cap-add sys_admin --security-opt label=disable \
    -v "$WORK/build_iso.sh":/src/build_iso.sh:ro \
    --mount type=image,source="$LIVE_IMAGE",dst=/rootfs \
    -v "$WORK/payload":/rootfs/var/lib/containers/storage:ro \
    -v "$OUT_DIR":/output \
    quay.io/fedora/fedora:latest bash -exo pipefail /src/build_iso.sh

iso="$(ls -t "$OUT_DIR"/*.iso | head -n1)"
[[ "$iso" == "$OUT_DIR/sloth-os.iso" ]] || mv -f "$iso" "$OUT_DIR/sloth-os.iso"
(cd "$OUT_DIR" && sha256sum sloth-os.iso > sloth-os.iso.sha256)
[[ -n "${SLOTH_OWNER:-}" ]] && chown -R "$SLOTH_OWNER" "$OUT_DIR"
echo "== Done: $OUT_DIR/sloth-os.iso ($(du -h "$OUT_DIR/sloth-os.iso" | cut -f1))"
