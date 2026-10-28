"""Whether the registry has a newer system image than the running one, asked without rpm-ostree.

rpm-ostree's own check ("upgrade --check", the CachedUpdate data) is blind on a machine with layered packages:
it cannot read the base image there ("failed to query container image base metadata: Missing
ostree.manifest-digest metadata on merge commit", 2026-10-28 on the gaming PC with nmap layered) and only looks at
the Fedora repositories, so it says "no updates" while a new Sloth OS waits in the registry. The real upgrade
works; only the check does not. Then the image's manifest in the registry is compared with the running one:
the registry gives an index with a manifest per architecture, and rpm-ostree keeps the digest of this machine's
one (container-image-reference-digest).
"""
import datetime
import hashlib
import json
import logging
import platform
import re
import subprocess

log = logging.getLogger("sloth-center.registry")

ARCH = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())


def is_blind(booted, cached):
    """Whether rpm-ostree's check could not see the image: packages are layered and its result has no
    manifest comparison."""
    layered = booted.get("requested-packages") or booted.get("packages")
    return bool(layered) and not (cached or {}).get("manifest-diff")


def image_ref(reference):
    """"ostree-image-signed:docker://ghcr.io/x:latest" -> "docker://ghcr.io/x:latest"; "" if it is not an image
    from a registry."""
    if "docker://" in reference:
        return "docker://" + reference.split("docker://", 1)[1]
    if reference.startswith("ostree-unverified-registry:"):
        return "docker://" + reference.split(":", 1)[1]
    return ""


def manifest_digests(raw, arch=ARCH):
    """The digests that stand for this machine's image in a manifest from the registry: in an index the
    manifests of this architecture, otherwise the manifest's own digest."""
    data = json.loads(raw)
    if isinstance(data, dict) and "manifests" in data:
        return {m.get("digest") for m in data["manifests"]
                if (m.get("platform") or {}).get("architecture") == arch}
    return {"sha256:" + hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()}


def _epoch(created):
    """"2026-10-28T20:20:31Z" -> seconds; 0 if it is not a date. The registry sometimes gives nanoseconds
    ("11:53:12.35967022Z"), which fromisoformat does not take everywhere: the fraction is dropped."""
    try:
        plain = re.sub(r"\.\d+", "", created).replace("Z", "+00:00")
        return int(datetime.datetime.fromisoformat(plain).timestamp())
    except (AttributeError, ValueError):
        return 0


def newer_image(booted, run=subprocess.run):
    """The newer image in the registry as {"timestamp": …} (what texts.version_text reads), or None: the same
    image, not an image from a registry, or the registry could not be asked (then nothing is claimed)."""
    ref = image_ref(str(booted.get("container-image-reference") or ""))
    current = booted.get("container-image-reference-digest")
    if not ref or not current:
        return None
    try:
        r = run(["skopeo", "inspect", "--raw", ref], capture_output=True, timeout=60)
        if r.returncode != 0:
            log.warning("skopeo inspect --raw %s: %s", ref, (r.stderr or b"")[-300:])
            return None
        if current in manifest_digests(r.stdout):
            return None
        info = run(["skopeo", "inspect", "--no-tags", ref], capture_output=True, text=True, timeout=60)
        created = json.loads(info.stdout).get("Created", "") if info.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        log.warning("registry check: %s", e)
        return None
    return {"timestamp": _epoch(created)}
