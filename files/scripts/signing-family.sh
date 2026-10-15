#!/usr/bin/env bash
# Aláírás-ellenőrzés mindkét Sloth OS változatra (a signing modul után fut).
# A BlueBuild signing modulja csak a saját image nevére tesz szabályt a policy.json-ba (minden más: reject).
# A változatok között váltunk (AMD/Intel <-> NVIDIA: Sloth Központ, sloth-nvidia-auto), ezért a másik
# változat aláírását is el kell fogadni. Mindkettőt ugyanaz a kulcs (cosign.pub) írja alá.
set -euo pipefail

REGISTRY=ghcr.io/bathorizsolt
NAMES=(sloth-os sloth-os-nvidia)
PKI=/etc/pki/containers
POLICY=/etc/containers/policy.json

key=""
for n in "${NAMES[@]}"; do
  [[ -f $PKI/$n.pub ]] && key=$PKI/$n.pub
done
[[ -n $key ]] || { echo "HIBA: nincs aláíró kulcs a $PKI mappában (a signing modul után kell futnia)" >&2; exit 1; }
[[ "$(jq -r '.default[0].type' "$POLICY")" == reject ]] || { echo "HIBA: a policy.json alapja nem reject" >&2; exit 1; }

for n in "${NAMES[@]}"; do
  [[ -f $PKI/$n.pub ]] || cp "$key" "$PKI/$n.pub"
  jq --arg image "$REGISTRY/$n" --arg key "$PKI/$n.pub" \
     '.transports.docker[$image] = [{"type": "sigstoreSigned", "keyPath": $key,
                                     "signedIdentity": {"type": "matchRepository"}}]' \
     "$POLICY" > /tmp/policy.json
  mv /tmp/policy.json "$POLICY"
  yaml=/etc/containers/registries.d/bathorizsolt-$n.yaml
  [[ -f $yaml ]] || printf 'docker:\n  %s:\n    use-sigstore-attachments: true\n' "$REGISTRY/$n" > "$yaml"
done
jq -e --arg a "$REGISTRY/sloth-os" --arg b "$REGISTRY/sloth-os-nvidia" \
   '.transports.docker[$a][0].type == "sigstoreSigned" and .transports.docker[$b][0].type == "sigstoreSigned"' "$POLICY"
ls /etc/containers/registries.d/
