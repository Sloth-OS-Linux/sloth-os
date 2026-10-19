#!/usr/bin/bash
# Sloth OS telepítő ISO építése helyben, Linuxon (rootful Podman).
# Fejlesztői segéd, nem kerül az image-be. Windowson: tools/build-iso.ps1, a CI-ben: .github/workflows/iso.yml
#
#   tools/build-iso.sh [image] [kimeneti mappa]
#
# Felhasználóként kell indítani: a GitHub CLI tokenjével lép be a ghcr.io-ra ("read:packages" jog kell,
# egyszer: gh auth refresh -h github.com -s read:packages), utána rendszergazdaként fut tovább (sudo,
# grafikus jelszókérővel, ha a SUDO_ASKPASS be van állítva).
#
# Környezeti változók:
#   SLOTH_BUILD_DIR   munkamappa és a Podman tárolója (alapból /var/tmp/sloth-iso-build; kb. 25–28 GB kell)
#   SLOTH_SQUASH=1    a telepítendő image rétegeinek összevonása egybe: a lecserélt / törölt fájlok (pl. a
#                     régi kernel) kiesnek, kisebb az ISO (becslés: 0,5–1 GB). Ára: a telepített gép első
#                     frissítése a teljes image-et letölti (a rétegei nem egyeznek a registryével). Kiadáshoz.
#   http(s)_proxy     a letöltésekhez; a konténerek is ezt használják (a gép hálózatán futnak)
set -euo pipefail

IMAGE="${1:-ghcr.io/bathorizsolt/sloth-os:latest}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$(realpath -m "${2:-$REPO/out}")"
WORK="${SLOTH_BUILD_DIR:-/var/tmp/sloth-iso-build}"

# A Titanoboa ISO-készítő scriptje rögzített commitról (frissítéskor: a SHA cseréje a .github/workflows/iso.yml-ben is)
TITANOBOA_COMMIT="5c457c3d0518bd17e754be0fd98a60d29d26abb4"
LIVE_IMAGE="localhost/sloth-os-live:latest"

# --- 1. Felhasználóként: belépési adatok, utána újraindulás rendszergazdaként ------------------
if [[ $EUID -ne 0 ]]; then
    user="$(gh api user --jq .login)" || { echo "A GitHub CLI nincs bejelentkezve (gh auth login)." >&2; exit 1; }
    auth="$(mktemp)"
    trap 'rm -f "$auth"' EXIT
    printf '{"auths":{"ghcr.io":{"auth":"%s"}}}\n' "$(printf '%s:%s' "$user" "$(gh auth token)" | base64 -w0)" > "$auth"
    sudo_args=(--preserve-env=http_proxy,https_proxy,HTTP_PROXY,HTTPS_PROXY,no_proxy,NO_PROXY,SLOTH_BUILD_DIR,SLOTH_SQUASH)
    [[ -n "${SUDO_ASKPASS:-}" ]] && sudo_args+=(-A)
    sudo "${sudo_args[@]}" SLOTH_REGISTRY_AUTH="$auth" SLOTH_OWNER="$(id -u):$(id -g)" \
        "${BASH_SOURCE[0]}" "$IMAGE" "$OUT_DIR"
    exit
fi

# --- 2. Rendszergazdaként ------------------------------------------------------------------------
mkdir -p "$WORK" "$OUT_DIR"
AUTH="$WORK/auth.json"
install -m 600 "${SLOTH_REGISTRY_AUTH:?}" "$AUTH"
# A kicsomagolt telepítendő image (kb. 12 GB) csak az ISO készítéséig kell
trap 'rm -f "$AUTH"; rm -rf "$WORK/payload-oci" "$WORK/payload"' EXIT

# A WSL-es Podman gépen (tools/build-iso.ps1) a systemd nem kezeli a konténerek cgroupjait, és nincs
# "pids" vezérlő: ott cgroupfs kell, és a konténerek cgroup nélkül indulnak (e nélkül a build első
# RUN lépése "Failed to set unit properties" hibával áll meg)
pm_opts=() run_opts=()
if grep -qi microsoft /proc/version; then
    pm_opts=(--cgroup-manager=cgroupfs)
    run_opts=(--cgroups=disabled)
fi
pm() { podman --root "$WORK/storage" --runroot "$WORK/run" "${pm_opts[@]}" "$@"; }

echo "== Alap image letöltése: $IMAGE"
pm pull --authfile "$AUTH" "$IMAGE"

echo "== Élő rendszer építése: $LIVE_IMAGE"
pm build --pull=never --network host --security-opt label=disable \
    --build-arg BASE_IMAGE="$IMAGE" -t "$LIVE_IMAGE" "$REPO/iso"

# A telepítendő image kicsomagolt konténertárolója egy külön mappába kerül (iso/payload.sh), amit az ISO
# készítésekor az élő rendszer /var/lib/containers/storage helyére csatolunk. Nem kell podman commit
# (az a lassú gépen egymaga másfél óra volt), és a fájlok változatlanul kerülnek az ISO-ba.
# A telepítendő image-et nem töltjük le újra, és átmeneti OCI-másolat sincs (az még kb. 12 GB volt): a
# kicsomagoló közvetlenül a már letöltött tárolóból olvas (becsatolva, containers-storage forrásként).
payload_src="$IMAGE"
if [[ "${SLOTH_SQUASH:-0}" == 1 ]]; then
    echo "== A telepítendő image rétegeinek összevonása"
    mkdir -p "$WORK/squash"
    printf 'FROM %s\n' "$IMAGE" > "$WORK/squash/Containerfile"
    pm build --pull=never --squash-all --network none --security-opt label=disable \
        -t localhost/sloth-os-payload:latest -f "$WORK/squash/Containerfile" "$WORK/squash"
    payload_src="localhost/sloth-os-payload:latest"
fi
echo "== Telepítendő image kicsomagolása"
rm -rf "$WORK/payload-oci" "$WORK/payload"
mkdir -p "$WORK/payload"
driver="$(pm info --format '{{.Store.GraphDriverName}}')"
pm run --rm "${run_opts[@]}" --privileged --network none \
    -v "$REPO/iso/payload.sh":/payload.sh:ro \
    -v "$WORK/storage":/outer/storage \
    -v "$WORK/payload":/var/lib/containers/storage \
    "$LIVE_IMAGE" bash /payload.sh "$IMAGE" "containers-storage:[$driver@/outer/storage+/run/outer]$payload_src"
[[ "$payload_src" == "$IMAGE" ]] || pm rmi "$payload_src"

echo "== ISO készítése (Titanoboa ${TITANOBOA_COMMIT:0:7})"
curl -fsSL -o "$WORK/build_iso.sh" \
    "https://raw.githubusercontent.com/ublue-os/titanoboa/${TITANOBOA_COMMIT}/build_iso.sh"
# Rejtett GRUB menü: alapból azonnal a Sloth OS indul, Escre jön elő (iso/iso.yaml)
grep -q "set menu_auto_hide=false" "$WORK/build_iso.sh" || { echo "A Titanoboa GRUB-sablonja megváltozott." >&2; exit 1; }
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
echo "== Kész: $OUT_DIR/sloth-os.iso ($(du -h "$OUT_DIR/sloth-os.iso" | cut -f1))"
