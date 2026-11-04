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

    def test_earlier_sloth_os_counts_as_free_space(self):
        # Windows shrunk by the first install, then the earlier Sloth OS right after it, then nothing free
        gib = 1024**3 // 512
        win = {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 200 * gib}
        old = [{"node": "/dev/testp3", "type": helper.ESP_TYPE, "name": "EFI-SYSTEM", "start": 206848 + 200 * gib,
                "size": 1 * gib},
               {"node": "/dev/testp4", "type": helper.ROOT_X86_64, "name": "root", "start": 206848 + 201 * gib,
                "size": 99 * gib}]
        parts = [{"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800}, win, *old]
        pt = {"label": "gpt", "sectorsize": 512, "partitions": parts, "firstlba": 2048,
              "lastlba": 206848 + 300 * gib - 1}
        with (patch.object(helper.Path, "is_dir", return_value=True),
              patch.object(helper, "table", return_value=pt),
              patch.object(helper, "release_disk"),
              patch.object(helper, "windows_esps", return_value=[{"path": "/dev/testp1", "uuid": "esp"}]),
              patch.object(helper, "previous_sloth", return_value=old),
              patch.object(helper, "fstype", side_effect=lambda dev: {"/dev/testp1": "vfat"}.get(dev, "ntfs")),
              patch.object(helper, "has_windows_system_files", side_effect=lambda dev: dev == "/dev/testp2"),
              patch.object(helper, "ntfs_info", return_value=(190 * 1024**3, ""))):
            result = helper.probe("/dev/test")
        self.assertEqual(result["previous"], ["/dev/testp3", "/dev/testp4"])
        self.assertNotIn("no_space", result["problems"])
        self.assertGreaterEqual(result["max"], 99 * 1024**3)

    def test_earlier_sloth_os_place_is_enough_with_windows_hibernated(self):
        # Windows shut down with fast startup after the first install: it cannot be made smaller, but the earlier
        # Sloth OS's place is enough, so installing next to it again is possible (Windows is not touched)
        gib = 1024**3 // 512
        win = {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 200 * gib}
        old = [{"node": "/dev/testp3", "type": helper.ESP_TYPE, "name": "EFI-SYSTEM", "start": 206848 + 200 * gib,
                "size": 1 * gib},
               {"node": "/dev/testp4", "type": helper.ROOT_X86_64, "name": "root", "start": 206848 + 201 * gib,
                "size": 99 * gib}]
        parts = [{"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800}, win, *old]
        pt = {"label": "gpt", "sectorsize": 512, "partitions": parts, "firstlba": 2048,
              "lastlba": 206848 + 300 * gib - 1}
        for problem in ("hibernated", "unclean", "dirty"):
            with (patch.object(helper.Path, "is_dir", return_value=True),
                  patch.object(helper, "table", return_value=pt),
                  patch.object(helper, "release_disk"),
                  patch.object(helper, "windows_esps", return_value=[{"path": "/dev/testp1", "uuid": "esp"}]),
                  patch.object(helper, "previous_sloth", return_value=old),
                  patch.object(helper, "fstype", side_effect=lambda dev: {"/dev/testp1": "vfat"}.get(dev, "ntfs")),
                  patch.object(helper, "has_windows_system_files", side_effect=lambda dev: dev == "/dev/testp2"),
                  patch.object(helper, "ntfs_info", return_value=(None, problem))):
                result = helper.probe("/dev/test")
            self.assertEqual(result["problems"], [], problem)
            self.assertGreaterEqual(result["max"], 99 * 1024**3)
            self.assertEqual(result["shrinkable"], 0)

    def _previous_and_unreadable_windows(self):
        gib = 1024**3 // 512
        win = {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 200 * gib}
        old = [{"node": "/dev/testp3", "type": helper.ESP_TYPE, "name": "EFI-SYSTEM", "start": 206848 + 200 * gib,
                "size": 1 * gib},
               {"node": "/dev/testp4", "type": helper.ROOT_X86_64, "name": "root", "start": 206848 + 201 * gib,
                "size": 99 * gib}]
        parts = [{"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800}, win, *old]
        pt = {"label": "gpt", "sectorsize": 512, "partitions": parts, "firstlba": 2048,
              "lastlba": 206848 + 300 * gib - 1}
        with (patch.object(helper.Path, "is_dir", return_value=True),
              patch.object(helper, "table", return_value=pt),
              patch.object(helper, "release_disk"),
              patch.object(helper, "windows_esps", return_value=[{"path": "/dev/testp1", "uuid": "esp"}]),
              patch.object(helper, "previous_sloth", return_value=old),
              patch.object(helper, "fstype", side_effect=lambda dev: {"/dev/testp1": "vfat"}.get(dev, "ntfs")),
              # the Windows volume could not be checked (its system files not read)
              patch.object(helper, "has_windows_system_files", return_value=False),
              patch.object(helper, "ntfs_info", return_value=(None, "unknown"))):
            return helper.probe("/dev/test")

    def test_earlier_sloth_os_place_is_enough_with_windows_unreadable(self):
        result = self._previous_and_unreadable_windows()
        self.assertEqual(result["problems"], [])
        self.assertGreaterEqual(result["max"], 99 * 1024**3)
        self.assertNotIn("windows", result)

    def test_windows_hibernated_without_free_space_still_blocks(self):
        gib = 1024**3 // 512
        win = {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 206848, "size": 200 * gib}
        parts = [{"node": "/dev/testp1", "type": helper.ESP_TYPE, "start": 2048, "size": 204800}, win]
        pt = {"label": "gpt", "sectorsize": 512, "partitions": parts, "firstlba": 2048,
              "lastlba": 206848 + 200 * gib - 1}
        with (patch.object(helper.Path, "is_dir", return_value=True),
              patch.object(helper, "table", return_value=pt),
              patch.object(helper, "release_disk"),
              patch.object(helper, "windows_esps", return_value=[{"path": "/dev/testp1", "uuid": "esp"}]),
              patch.object(helper, "previous_sloth", return_value=[]),
              patch.object(helper, "fstype", side_effect=lambda dev: {"/dev/testp1": "vfat"}.get(dev, "ntfs")),
              patch.object(helper, "has_windows_system_files", side_effect=lambda dev: dev == "/dev/testp2"),
              patch.object(helper, "ntfs_info", return_value=(None, "hibernated"))):
            result = helper.probe("/dev/test")
        self.assertEqual(result["problems"], ["hibernated"])

    def test_earlier_sloth_os_on_windows_efi_partition(self):
        # the advanced way put Sloth OS on Windows' EFI partition: only its system partition is replaced
        win_esp = {"node": "/dev/testp1", "type": helper.ESP_TYPE, "name": "Basic data partition", "uuid": "WIN-ESP"}
        root = {"node": "/dev/testp4", "type": helper.ROOT_X86_64, "name": "root"}
        pt = {"partitions": [win_esp, {"node": "/dev/testp3", "type": helper.LINUX_DATA}, root]}
        with (patch.object(helper, "fstype", side_effect=lambda dev: "vfat" if dev == "/dev/testp1" else "btrfs"),
              patch.object(helper, "_esp_has", return_value=True),
              patch.object(helper, "_is_sloth_root", return_value=True)):
            previous = helper.previous_sloth(pt)
        self.assertEqual([p["node"] for p in previous], ["/dev/testp4"])
        self.assertEqual(previous[0]["shared_esp"], "WIN-ESP")
        # another Linux on Windows' EFI partition is not taken for Sloth OS
        with (patch.object(helper, "fstype", side_effect=lambda dev: "vfat" if dev == "/dev/testp1" else "btrfs"),
              patch.object(helper, "_esp_has", return_value=True),
              patch.object(helper, "_is_sloth_root", return_value=False)):
            self.assertEqual(helper.previous_sloth(pt), [])

    def test_shared_efi_removal_keeps_windows_boot_entry(self):
        listing = ("BootCurrent: 0001\n"
                   "Boot0000* Windows Boot Manager\tHD(1,GPT,win-esp,0x800,0x64000)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n"
                   "Boot0001* Fedora\tHD(1,GPT,win-esp,0x800,0x64000)/File(\\EFI\\fedora\\shimx64.efi)\n")
        deleted = []

        def fake_run(cmd, *a, **k):
            class R:
                returncode, stdout, stderr = 0, listing if cmd[:2] == ["efibootmgr", "--verbose"] else "", ""
            if "--delete-bootnum" in cmd:
                deleted.append(cmd[2])
            return R()
        previous = [{"node": "/dev/testp4", "shared_esp": "WIN-ESP"}]
        with (patch.object(helper.Path, "is_dir", return_value=True),
              patch.object(helper.subprocess, "run", side_effect=fake_run),
              patch.object(helper, "run"),
              patch.object(helper, "partnum", return_value=4)):
            helper.remove_previous("/dev/test", previous)
        self.assertEqual(deleted, ["0001"])

    def test_a_busy_mount_point_does_not_stop_the_survey(self):
        # the live desktop looks at a new mount for a moment: umount says busy and the folder cannot be removed
        calls = []

        def fake_run(cmd, *a, **k):
            calls.append(cmd[:2])
            class R:
                returncode = 0 if cmd[0] == "mount" or "--lazy" in cmd else 32
            return R()
        with (patch.object(helper.subprocess, "run", side_effect=fake_run),
              patch.object(helper.time, "sleep"),
              patch.object(helper.Path, "rmdir", side_effect=OSError(16, "Device or resource busy"))):
            with helper.mounted_ro("/dev/testp1") as mnt:
                self.assertIsNotNone(mnt)
        self.assertIn(["umount", "--lazy"], calls)

    def test_earlier_sloth_os_needs_its_system_partition(self):
        # an EFI partition with our name alone is not enough (nothing is mounted to find that out)
        parts = [{"node": "/dev/testp3", "type": helper.ESP_TYPE, "name": "EFI-SYSTEM", "start": 2048, "size": 1}]
        with patch.object(helper, "fstype", side_effect=AssertionError("must not look")):
            self.assertEqual(helper.previous_sloth({"partitions": parts}), [])

    def manual(self, root_size, esp_type=None, esp_fs="vfat"):
        """partition_manual on a fake GPT disk: -> (the sfdisk inputs, the result or the failure key)."""
        gib = 1024**3 // 512
        parts = [{"node": "/dev/testp1", "type": esp_type or helper.ESP_TYPE, "start": 2048, "size": gib},
                 {"node": "/dev/testp2", "type": helper.LINUX_DATA, "start": 2048 + gib, "size": root_size * gib}]
        after = parts + [{"node": "/dev/testp3", "type": helper.LINUX_DATA,
                          "start": 2048 + gib + root_size * gib - helper.scratch_bytes // 512,
                          "size": helper.scratch_bytes // 512}]
        tables = iter([{"label": "gpt", "sectorsize": 512, "partitions": parts},
                       {"label": "gpt", "sectorsize": 512, "partitions": after}])
        inputs = []
        with (patch.object(helper, "table", side_effect=lambda disk: next(tables)),
              patch.object(helper, "fstype", side_effect=lambda dev: esp_fs if dev == "/dev/testp1" else ""),
              patch.object(helper, "windows_esps", return_value=[]),
              patch.object(helper, "partnum", side_effect=lambda disk, node: int(node[-1])),
              patch.object(helper.subprocess, "run"),
              patch.object(helper, "run", side_effect=lambda cmd, **kw: inputs.append(kw.get("input"))),
              patch.object(helper, "fail", side_effect=lambda key, detail="": (_ for _ in ()).throw(Failed(key)))):
            try:
                return inputs, helper.partition_manual("/dev/test", "/dev/testp2", "/dev/testp1")
            except Failed as e:
                return inputs, str(e)

    def test_manual_splits_the_work_area_off_the_end(self):
        inputs, (parts, windows_esp) = self.manual(100)
        self.assertEqual((parts["root"], parts["scratch"], parts["esp"]), ("/dev/testp2", "/dev/testp3", "/dev/testp1"))
        self.assertTrue(parts["keep_esp"])   # an EFI partition with FAT is kept, not formatted
        self.assertIn("name=\"root\"", inputs[0])
        self.assertIn("sloth-install-tmp", inputs[1])

    def test_manual_refuses_a_small_system_partition(self):
        self.assertEqual(self.manual(45)[1], "error.manual_small")

    def test_manual_refuses_a_partition_that_is_not_efi(self):
        self.assertEqual(self.manual(100, esp_type=helper.LINUX_DATA)[1], "error.manual_esp")
        self.assertEqual(self.manual(100, esp_fs="ntfs")[1], "error.manual_esp")

    def ntfs_problem(self, output):
        result = type("R", (), {"returncode": 1, "stdout": output, "stderr": ""})()
        with (patch.object(helper, "hibernated", return_value=False),
              patch.object(helper.subprocess, "run", return_value=result)):
            return helper.ntfs_info("/dev/testp3")[1]

    def test_unclean_journal_is_not_a_disk_check(self):
        # ntfsresize's journal message mentions chkdsk too: it used to be taken for a due disk check
        self.assertEqual(self.ntfs_problem(
            "The NTFS journal file is unclean. Please shutdown Windows properly before\n"
            "using this software! Note, if you have run chkdsk previously then boot\n"
            "Windows again which will automatically initialize the journal correctly.\n"), "unclean")
        self.assertEqual(self.ntfs_problem("Volume is scheduled for check.\nRun chkdsk /f and please try again"), "dirty")
        self.assertEqual(self.ntfs_problem("The NTFS partition is hibernated. Windows must be resumed"), "hibernated")

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


class Failed(Exception):
    pass


class ExtraDiskChoiceTest(unittest.TestCase):
    """--extra-disk: a disk with Windows data is never changed, whatever the UI sends."""

    def parse(self, values, filesystems, target="/dev/sda"):
        def fail(key, detail=""):
            raise Failed(detail)
        with (patch.object(helper, "whole_disk", return_value=True),
              patch.object(helper, "disk_filesystems", side_effect=lambda disk: filesystems.get(disk, [])),
              patch.object(helper, "fail", side_effect=fail)):
            return helper.parse_extra(values, target)

    def test_choices_are_parsed(self):
        result = self.parse(["erase:/dev/sdb", "keep:/dev/sdc"],
                            {"/dev/sdb": [], "/dev/sdc": [("/dev/sdc1", "ext4")]})
        self.assertEqual(result, [("erase", "/dev/sdb", []), ("keep", "/dev/sdc", ["/dev/sdc1"])])

    def test_only_chosen_linux_partitions_are_kept(self):
        disk = {"/dev/sdb": [("/dev/sdb1", "ext4"), ("/dev/sdb2", "btrfs"), ("/dev/sdb3", "exfat")]}
        self.assertEqual(self.parse(["keep:/dev/sdb:/dev/sdb2"], disk), [("keep", "/dev/sdb", ["/dev/sdb2"])])
        with self.assertRaises(Failed):
            self.parse(["keep:/dev/sdb:/dev/sdb3"], disk)   # not a Linux file system
        with self.assertRaises(Failed):
            self.parse(["keep:/dev/sdb:/dev/sdc1"], disk)   # not on this disk

    def test_windows_data_is_never_erased(self):
        for fs in ("ntfs", "bitlocker"):
            with self.assertRaises(Failed):
                self.parse(["erase:/dev/sdb"], {"/dev/sdb": [("/dev/sdb1", "vfat"), ("/dev/sdb2", fs)]})

    def test_windows_data_is_never_mounted(self):
        disk = {"/dev/sdb": [("/dev/sdb1", "ext4"), ("/dev/sdb2", "ntfs"), ("/dev/sdb3", "bitlocker")]}
        # the Linux partition next to Windows can be used, the Windows ones never
        self.assertEqual(self.parse(["keep:/dev/sdb"], disk), [("keep", "/dev/sdb", ["/dev/sdb1"])])
        for part in ("/dev/sdb2", "/dev/sdb3"):
            with self.assertRaises(Failed):
                self.parse([f"keep:/dev/sdb:{part}"], disk)

    def test_keep_needs_a_linux_file_system(self):
        with self.assertRaises(Failed):
            self.parse(["keep:/dev/sdb"], {"/dev/sdb": [("/dev/sdb1", "exfat")]})

    def test_target_and_duplicates_are_rejected(self):
        for values in (["erase:/dev/sda"], ["erase:/dev/sdb", "keep:/dev/sdb"], ["format:/dev/sdb"]):
            with self.assertRaises(Failed):
                self.parse(values, {"/dev/sdb": [("/dev/sdb1", "ext4")]})

    def test_mount_names_are_safe_and_unique(self):
        used = set()
        self.assertEqual(helper._mount_name("Games & Stuff", used), "games-stuff")
        self.assertEqual(helper._mount_name("games stuff", used), "games-stuff-2")
        self.assertEqual(helper._mount_name("Ünnep", used), "nnep")
        self.assertEqual(helper._mount_name("!!!", used), "disk")


if __name__ == "__main__":
    unittest.main(verbosity=2)
