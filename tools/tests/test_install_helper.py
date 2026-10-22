#!/usr/bin/env python3
"""Safety checks for the installer helper's Windows-disk survey (no disk access)."""
import importlib.machinery
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
HELPER_PATH = REPO / "iso/files/usr/libexec/sloth-os/sloth-install-helper"
loader = importlib.machinery.SourceFileLoader("sloth_install_helper", str(HELPER_PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)


class WindowsDiskSurveyTest(unittest.TestCase):
    def survey(self, partitions, filesystems, windows_parts=(), esp_count=1):
        pt = {"label": "gpt", "sectorsize": 512, "partitions": partitions}
        with (patch.object(helper.Path, "is_dir", return_value=True),
              patch.object(helper, "table", return_value=pt),
              patch.object(helper, "release_disk"),
              patch.object(helper, "windows_esps", return_value=[{"path": "/dev/testp1", "uuid": "esp"}]
                   * esp_count),
              patch.object(helper, "free_regions", return_value=[(2048, 200 * 1024**3 // 512)]),
              patch.object(helper, "fstype", side_effect=lambda dev: filesystems[dev]),
              patch.object(helper, "has_windows_system_files", side_effect=lambda dev: dev in windows_parts),
              patch.object(helper, "ntfs_info", return_value=(100 * 1024**3, "")),
              patch.object(helper, "gap_after", return_value=0)):
            return helper.probe("/dev/test")

    def test_data_only_ntfs_is_not_offered_as_windows(self):
        parts = [
            {"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800},
            {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 400000000},
        ]
        result = self.survey(parts, {"/dev/testp1": "vfat", "/dev/testp2": "ntfs"})
        self.assertIn("unknown", result["problems"])
        self.assertNotIn("windows", result)
        self.assertEqual(result["shrinkable"], 0)

    def test_identified_windows_partition_is_the_only_shrink_target(self):
        parts = [
            {"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800},
            {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 400000000},
            {"node": "/dev/testp3", "type": helper.LINUX_DATA, "start": 400206848, "size": 300000000},
        ]
        result = self.survey(parts, {"/dev/testp1": "vfat", "/dev/testp2": "ntfs",
                                     "/dev/testp3": "ntfs"}, windows_parts=["/dev/testp3"])
        self.assertEqual(result["windows"]["path"], "/dev/testp3")
        self.assertNotIn("unknown", result["problems"])

    def test_ambiguous_windows_boot_partitions_are_rejected(self):
        parts = [{"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800}]
        result = self.survey(parts, {"/dev/testp1": "vfat"}, esp_count=2)
        self.assertIn("unknown", result["problems"])
        self.assertEqual(result["windowsEsp"], "")

    def test_efi_types_are_restored_after_partial_failure(self):
        partitions = [
            {"node": "/dev/testp1", "type": helper.ESP_TYPE},
            {"node": "/dev/testp2", "type": helper.ESP_TYPE},
        ]
        with (patch.object(helper, "table", return_value={"partitions": partitions}),
              patch.object(helper, "partnum", side_effect=[1, 2]),
              patch.object(helper, "run", side_effect=[None, SystemExit(1)]),
              patch.object(helper, "restore_esps") as restore):
            with self.assertRaises(SystemExit):
                helper.hide_other_esps("/dev/test", own_partn=3)
        restore.assert_called_once_with("/dev/test", [(1, "/dev/testp1"), (2, "/dev/testp2")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
