#!/usr/bin/env python3
"""Installer attempts (sloth_exe/heal.py install_plan, installer records); no Wine or Proton needed."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="sloth-install-heal-"))
os.environ["HOME"] = str(TMP)
os.environ["XDG_DATA_HOME"] = str(TMP / "data")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-exe"))

from sloth_exe import heal  # noqa: E402

heal.INSTALLERS = TMP / "installers.json"
# Two installed UMU-Proton versions, the newest is used
for name in ("UMU-Proton-9.0-3", "UMU-Proton-10.0-2"):
    (TMP / "data/Steam/compatibilitytools.d" / name).mkdir(parents=True, exist_ok=True)
    (TMP / "data/Steam/compatibilitytools.d" / name / "proton").write_text("")
heal.COMPAT_DIRS = [TMP / "data/Steam/compatibilitytools.d"]
NEW = "UMU-Proton-10.0-2"


def keys(plan):
    return [a.key for a in plan]


class InstallPlanTest(unittest.TestCase):
    def setUp(self):
        heal.INSTALLERS.unlink(missing_ok=True)

    def test_default_order(self):
        self.assertEqual(keys(heal.install_plan("k")),
                         [f"{NEW}|default", f"{NEW}|nofsync", f"{NEW}|wined3d", "GE-Proton|default"])

    def test_existing_environment_keeps_its_proton(self):
        # reinstalling into a program's folder: no switch to another Proton version (nothing may break there)
        self.assertEqual(keys(heal.install_plan("k", fresh=False)),
                         [f"{NEW}|default", f"{NEW}|nofsync", f"{NEW}|wined3d"])

    def test_what_worked_goes_first_and_failures_are_skipped(self):
        heal.save_installer_record("k", {"good": {"proton": NEW, "profile": "wined3d"},
                                         "failed": [f"{NEW}|default"], "fixes": [["verb", "vcrun2022"]]})
        plan = heal.install_plan("k")
        self.assertEqual(keys(plan), [f"{NEW}|wined3d", f"{NEW}|nofsync", "GE-Proton|default"])
        self.assertIn(("verb", "vcrun2022"), plan[0].fixes)

    def test_shared_knowledge_suggestion(self):
        plan = heal.install_plan("k", suggest=(heal.UMU_LINE, "nofsync", [("verb", "dotnet48")]))
        self.assertEqual(plan[0].key, f"{NEW}|nofsync")
        self.assertIn(("verb", "dotnet48"), plan[0].fixes)

    def test_records_are_per_installer(self):
        heal.save_installer_record("a", {"good": {"proton": NEW, "profile": "nofsync"}})
        heal.save_installer_record("b", {"failed": [f"{NEW}|default"]})
        self.assertEqual(heal.installer_record("a")["good"]["profile"], "nofsync")
        self.assertEqual(heal.installer_record("c"), {})
        self.assertEqual(heal.install_plan("b")[0].key, f"{NEW}|nofsync")


if __name__ == "__main__":
    unittest.main(verbosity=2)
