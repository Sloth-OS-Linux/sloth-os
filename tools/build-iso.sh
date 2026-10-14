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
#   SLOTH_BUILD_DIR   munkamappa és a Podman tárolója (alapból /var/tmp/sloth-iso-build; kb. 40 GB kell)
#   http(s)_proxy     a letöltésekhez; a konténerek is ezt használják (a gép hálózatán futnak)
set -euo pipefail

IMAGE="${1:-ghcr.io/bathorizsolt/sloth-os:latest}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$(realpath -m "${2:-$REPO/out}")"
WORK="${SLOTH_BUILD_DIR:-/var/tmp/sloth-iso-build}"

# A Titanoboa ISO-készítő scriptje rögzített commitról (frissítéskor: a SHA cseréje, a többi build-scriptben is)
TITANOBOA_COMMIT="5c457c3d0518bd17e754be0fd98a60d29d26abb4"
LIVE_IMAGE="localhost/sloth-os-live:latest"

# --- 1. Felhasználóként: belépési adatok, utána újraindulás rendszergazdaként ------------------
if [[ $EUID -ne 0 ]]; then
    user="$(gh api user --jq .login)" || { echo "A GitHub CLI nincs bejelentkezve (gh auth login)." >&2; exit 1; }
    auth="$(mktemp)"
    trap 'rm -f "$auth"' EXIT
    printf '{"auths":{"ghcr.io":{"auth":"%s"}}}\n' "$(printf '%s:%s' "$user" "$(gh auth token)" | base64 -w0)" > "$auth"
    sudo_args=(--preserve-env=http_proxy,https_proxy,HTTP_PROXY,HTTPS_PROXY,no_proxy,NO_PROXY,SLOTH_BUILD_DIR)
    [[ -n "${SUDO_ASKPASS:-}" ]] && sudo_args+=(-A)
    sudo "${sudo_args[@]}" SLOTH_REGISTRY_AUTH="$auth" SLOTH_OWNER="$(id -u):$(id -g)" \
        "${BASH_SOURCE[0]}" "$IMAGE" "$OUT_DIR"
    exit
fi

# --- 2. Rendszergazdaként ------------------------------------------------------------------------
mkdir -p "$WORK" "$OUT_DIR"
AUTH="$WORK/auth.json"
install -m 600 "${SLOTH_REGISTRY_AUTH:?}" "$AUTH"
trap 'rm -f "$AUTH"; rm -rf "$WORK/payload-oci"' EXIT

pm() { podman --root "$WORK/storage" --runroot "$WORK/run" "$@"; }

echo "== Alap image letöltése: $IMAGE"
pm pull --authfile "$AUTH" "$IMAGE"

echo "== Élő rendszer építése: $LIVE_IMAGE"
pm build --pull=never --network host --security-opt label=disable \
    --build-arg BASE_IMAGE="$IMAGE" -t "$LIVE_IMAGE" "$REPO/iso"

# Második lépés privilegizált konténerben: a telepítendő image és a Firefox (iso/payload.sh).
# A telepítendő image-et nem töltjük le újra: a már letöltöttet adjuk át OCI-mappaként.
echo "== Telepítendő image és Firefox hozzáadása"
rm -rf "$WORK/payload-oci"
pm save --format oci-dir -o "$WORK/payload-oci" "$IMAGE"
pm rm -f sloth-live-payload >/dev/null 2>&1 || true
pm run --privileged --network host --name sloth-live-payload \
    -v "$AUTH":/run/secrets/registry-auth:ro \
    -v "$REPO/iso/payload.sh":/payload.sh:ro \
    -v "$WORK/payload-oci":/payload-oci:ro \
    "$LIVE_IMAGE" bash /payload.sh "$IMAGE" "$IMAGE" oci:/payload-oci
pm commit sloth-live-payload "$LIVE_IMAGE"
pm rm sloth-live-payload
rm -rf "$WORK/payload-oci"

echo "== ISO készítése (Titanoboa ${TITANOBOA_COMMIT:0:7})"
curl -fsSL --limit-rate 10M -o "$WORK/build_iso.sh" \
    "https://raw.githubusercontent.com/ublue-os/titanoboa/${TITANOBOA_COMMIT}/build_iso.sh"
# Rejtett GRUB menü: alapból azonnal a Sloth OS indul, Escre jön elő (iso/iso.yaml)
grep -q "set menu_auto_hide=false" "$WORK/build_iso.sh" || { echo "A Titanoboa GRUB-sablonja megváltozott." >&2; exit 1; }
sed -i "s/set menu_auto_hide=false/set timeout_style=hidden/" "$WORK/build_iso.sh"
rm -f "$OUT_DIR"/*.iso
pm run --rm --network host --cap-add sys_admin --security-opt label=disable \
    -v "$WORK/build_iso.sh":/src/build_iso.sh:ro \
    --mount type=image,source="$LIVE_IMAGE",dst=/rootfs \
    -v "$OUT_DIR":/output \
    quay.io/fedora/fedora:latest bash -exo pipefail /src/build_iso.sh

iso="$(ls -t "$OUT_DIR"/*.iso | head -n1)"
[[ "$iso" == "$OUT_DIR/sloth-os.iso" ]] || mv -f "$iso" "$OUT_DIR/sloth-os.iso"
(cd "$OUT_DIR" && sha256sum sloth-os.iso > sloth-os.iso.sha256)
[[ -n "${SLOTH_OWNER:-}" ]] && chown -R "$SLOTH_OWNER" "$OUT_DIR"
echo "== Kész: $OUT_DIR/sloth-os.iso ($(du -h "$OUT_DIR/sloth-os.iso" | cut -f1))"
