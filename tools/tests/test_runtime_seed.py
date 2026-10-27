#!/usr/bin/env python3
"""The bundled Proton and runtime (windows-runtime-seed): copied on an installed system, linked in the live system."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "files/system/usr/libexec/sloth-os/windows-runtime-seed"


class RuntimeSeed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src = root / "usr/share/sloth-os/windows-runtime"
        (self.src / "UMU-Proton-10.0-3").mkdir(parents=True)
        (self.src / "UMU-Proton-10.0-3/proton").write_text("#!/bin/sh\n")
        (self.src / "steamrt3").mkdir()
        (self.src / "steamrt3/VERSIONS.txt").write_text("sniper_platform_3.0.20261001\n")
        (self.src / "steamrt3/_v2-entry-point").write_text("")
        self.data = root / "home/.local/share"
        self.cmdline = root / "cmdline"

    def tearDown(self):
        for d, _, files in os.walk(self.tmp.name):
            os.chmod(d, 0o755)
        self.tmp.cleanup()

    def run_seed(self, cmdline):
        self.cmdline.write_text(cmdline)
        env = {**os.environ, "SLOTH_RUNTIME_SRC": str(self.src), "SLOTH_CMDLINE": str(self.cmdline),
               "XDG_DATA_HOME": str(self.data), "HOME": str(self.data.parent.parent)}
        r = subprocess.run(["bash", str(SEED)], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.data / "Steam/compatibilitytools.d/UMU-Proton-10.0-3", self.data / "umu/steamrt3"

    def test_installed_system_copies(self):
        proton, runtime = self.run_seed("BOOT_IMAGE=/vmlinuz root=UUID=x quiet")
        self.assertTrue(proton.is_dir() and not proton.is_symlink())
        self.assertTrue((runtime / ".installed.ok").is_file() and not runtime.is_symlink())
        self.assertTrue((runtime / "umu").is_symlink())

    def test_live_system_links(self):
        proton, runtime = self.run_seed("root=live:CDLABEL=SlothOS-Live rd.live.image quiet")
        self.assertTrue(proton.is_symlink())
        self.assertEqual(proton.resolve(), (self.src / "UMU-Proton-10.0-3").resolve())
        self.assertTrue(runtime.is_symlink())
        self.assertTrue((runtime / ".installed.ok").is_file())
        self.assertEqual(os.readlink(runtime / "umu"), "_v2-entry-point")

    @unittest.skipIf(os.geteuid() == 0, "root can write everywhere")
    def test_live_but_read_only_copies(self):
        # like the installed system's /usr: the folder cannot be written (its contents keep their usual rights)
        os.chmod(self.src, 0o555)
        proton, runtime = self.run_seed("rd.live.image")
        self.assertFalse(proton.is_symlink())
        self.assertFalse(runtime.is_symlink())

    def test_second_run_changes_nothing(self):
        self.run_seed("rd.live.image")
        proton, runtime = self.run_seed("rd.live.image")
        self.assertTrue(proton.is_symlink() and runtime.is_symlink())


if __name__ == "__main__":
    unittest.main()
