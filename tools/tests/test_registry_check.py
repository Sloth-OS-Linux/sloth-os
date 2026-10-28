#!/usr/bin/env python3
"""The update check that asks the registry (sloth_center.registry_check): when rpm-ostree's check is blind
(layered packages), the running image's digest is compared with the registry's index."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import registry_check as rc  # noqa: E402

RUNNING = "sha256:5b0137d96cefc5749fe825ffdd10a46843270b225cd5220897a64ead570582b2"
BOOTED = {"container-image-reference": "ostree-image-signed:docker://ghcr.io/sloth-os-linux/sloth-os-nvidia:latest",
          "container-image-reference-digest": RUNNING, "requested-packages": ["nmap"]}


def index(*amd64, other=()):
    return json.dumps({"mediaType": "application/vnd.oci.image.index.v1+json", "manifests":
                       [{"digest": d, "platform": {"architecture": "amd64", "os": "linux"}} for d in amd64]
                       + [{"digest": d, "platform": {"architecture": "unknown", "os": "unknown"}} for d in other]}
                      ).encode()


def registry(raw, created="2026-10-28T20:20:31Z", fail=False):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if fail:
            return subprocess.CompletedProcess(cmd, 1, b"", b"503 first byte timeout")
        if "--raw" in cmd:
            return subprocess.CompletedProcess(cmd, 0, raw, b"")
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"Created": created}), "")
    run.calls = calls
    return run


class RegistryCheck(unittest.TestCase):
    def test_blind_only_with_layered_packages_and_no_manifest_diff(self):
        self.assertTrue(rc.is_blind(BOOTED, {}))
        self.assertTrue(rc.is_blind(BOOTED, {"ref-has-new-commit": False}))
        self.assertFalse(rc.is_blind(BOOTED, {"manifest-diff": {"n-added": 0}}))
        self.assertFalse(rc.is_blind({**BOOTED, "requested-packages": []}, {}))

    def test_image_ref(self):
        self.assertEqual(rc.image_ref(BOOTED["container-image-reference"]),
                         "docker://ghcr.io/sloth-os-linux/sloth-os-nvidia:latest")
        self.assertEqual(rc.image_ref("ostree-unverified-registry:ghcr.io/x/y:latest"), "docker://ghcr.io/x/y:latest")
        self.assertEqual(rc.image_ref("fedora:fedora/44/x86_64/kinoite"), "")

    def test_same_image_is_no_update(self):
        run = registry(index(RUNNING, other=["sha256:attestation"]))
        self.assertIsNone(rc.newer_image(BOOTED, run))
        self.assertEqual(len(run.calls), 1)          # the date is only asked for a newer one

    def test_newer_image(self):
        newer = rc.newer_image(BOOTED, registry(index("sha256:new", other=[RUNNING])))
        self.assertEqual(newer, {"timestamp": 1793218831})   # 2026-10-28 20:20:31 UTC

    def test_a_single_manifest_is_compared_by_its_own_digest(self):
        raw = b'{"schemaVersion": 2, "config": {}}'
        import hashlib
        same = {**BOOTED, "container-image-reference-digest": "sha256:" + hashlib.sha256(raw).hexdigest()}
        self.assertIsNone(rc.newer_image(same, registry(raw)))
        self.assertIsNotNone(rc.newer_image(BOOTED, registry(raw)))

    def test_nothing_is_claimed_when_the_registry_does_not_answer(self):
        self.assertIsNone(rc.newer_image(BOOTED, registry(b"", fail=True)))
        self.assertIsNone(rc.newer_image(BOOTED, registry(b"not json")))
        self.assertIsNone(rc.newer_image({**BOOTED, "container-image-reference": "fedora:x"}, registry(index())))
        self.assertIsNone(rc.newer_image({**BOOTED, "container-image-reference-digest": ""}, registry(index())))

    def test_epoch(self):
        self.assertEqual(rc._epoch("2026-10-28T11:53:12.35967022Z"), 1793188392)   # nanoseconds, as ghcr gives
        self.assertEqual(rc._epoch("2026-10-28T11:53:12Z"), 1793188392)
        self.assertEqual(rc._epoch(""), 0)


if __name__ == "__main__":
    unittest.main()
