#!/usr/bin/env bash
# Signature verification for both Sloth OS variants (runs after the signing module).
# BlueBuild's signing module only puts a rule for its own image name into policy.json (everything else: reject).
# We switch between the variants (AMD/Intel <-> NVIDIA: Sloth Center, sloth-nvidia-auto), so the other
# variant's signature must be accepted too. Both are signed by the same key (cosign.pub).
set -euo pipefail

REGISTRY=ghcr.io/sloth-os-linux
NAMES=(sloth-os sloth-os-nvidia)
PKI=/etc/pki/containers
POLICY=/etc/containers/policy.json

key=""
for n in "${NAMES[@]}"; do
  [[ -f $PKI/$n.pub ]] && key=$PKI/$n.pub
done
[[ -n $key ]] || { echo "ERROR: no signing key in the $PKI folder (it must run after the signing module)" >&2; exit 1; }
[[ "$(jq -r '.default[0].type' "$POLICY")" == reject ]] || { echo "ERROR: the default of policy.json is not reject" >&2; exit 1; }

for n in "${NAMES[@]}"; do
  [[ -f $PKI/$n.pub ]] || cp "$key" "$PKI/$n.pub"
  jq --arg image "$REGISTRY/$n" --arg key "$PKI/$n.pub" \
     '.transports.docker[$image] = [{"type": "sigstoreSigned", "keyPath": $key,
                                     "signedIdentity": {"type": "matchRepository"}}]' \
     "$POLICY" > /tmp/policy.json
  mv /tmp/policy.json "$POLICY"
  yaml=/etc/containers/registries.d/sloth-os-linux-$n.yaml
  [[ -f $yaml ]] || printf 'docker:\n  %s:\n    use-sigstore-attachments: true\n' "$REGISTRY/$n" > "$yaml"
done
jq -e --arg a "$REGISTRY/sloth-os" --arg b "$REGISTRY/sloth-os-nvidia" \
   '.transports.docker[$a][0].type == "sigstoreSigned" and .transports.docker[$b][0].type == "sigstoreSigned"' "$POLICY"
ls /etc/containers/registries.d/
