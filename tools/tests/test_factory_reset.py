#!/usr/bin/env python3
"""A gép alaphelyzetbe állítása (files/system/usr/libexec/sloth-os/factory-reset): az /etc visszaállítása,
a kernelparaméterek és az asztal beállításainak áthelyezése, ideiglenes mappákban.

Linuxon fut:
  wsl -d podman-machine-default -- python3 -I /mnt/c/Users/batho/sloth-os/tools/tests/test_factory_reset.py
"""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_path = str(REPO / "files/system/usr/libexec/sloth-os/factory-reset")
_loader = importlib.machinery.SourceFileLoader("factory_reset", _path)
_spec = importlib.util.spec_from_loader("factory_reset", _loader)
fr = importlib.util.module_from_spec(_spec)
_loader.exec_module(fr)


def write(path, text="", mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(mode)


class ResetEtcTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.defaults, self.etc = self.tmp / "usr-etc", self.tmp / "etc"
        d = self.defaults
        write(d / "passwd", "root:x:0:0::/root:/bin/bash\n")
        write(d / "locale.conf", "LANG=en_US.UTF-8\n")
        write(d / "systemd/zram-generator.conf", "[zram0]\n")
        write(d / "sudoers.d/.keep")
        write(d / "polkit-1/rules.d/50-default.rules", "x")
        write(d / "NetworkManager/NetworkManager.conf", "[main]\n")
        (d / "NetworkManager/system-connections").mkdir(parents=True)
        (d / "ssh").mkdir()
        os.symlink("../usr/share/zoneinfo/UTC", d / "localtime")
        os.symlink("../run/systemd/resolve/stub-resolv.conf", d / "resolv.conf")
        (d / "systemd/system/multi-user.target.wants").mkdir(parents=True)
        os.symlink("/usr/lib/systemd/system/a.service", d / "systemd/system/multi-user.target.wants/a.service")
        shutil.copytree(d, self.etc, symlinks=True)
        # a felhasználó / a gép változtatásai
        e = self.etc
        write(e / "passwd", "root:x:0:0::/root:/bin/bash\nanna:x:1000:1000::/var/home/anna:/bin/bash\n")
        write(e / "locale.conf", "LANG=hu_HU.UTF-8\n")
        write(e / "systemd/zram-generator.conf", "# sloth-os: more\n")
        write(e / "sudoers.d/sloth-admin", "anna ALL=(ALL) NOPASSWD: ALL\n", 0o440)
        write(e / "polkit-1/rules.d/49-sloth-admin.rules", "y")
        write(e / "NetworkManager/system-connections/Otthon.nmconnection", "psk=titok\n", 0o600)
        write(e / "ssh/ssh_host_ed25519_key", "kulcs", 0o600)
        write(e / "sloth-os/snapshots.json", '{"enabled": false}\n')
        write(e / "sloth-os/admin-policy.json", "{}\n")
        write(e / "sloth-os/pin/anna.json", "{}\n")
        os.unlink(e / "polkit-1/rules.d/50-default.rules")
        (e / "systemd/system/multi-user.target.wants/a.service").unlink()
        os.symlink("/usr/lib/systemd/system/b.service", e / "systemd/system/multi-user.target.wants/b.service")
        os.chmod(e / "NetworkManager/NetworkManager.conf", 0o600)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def reset(self, mode):
        return fr.reset_etc(self.etc, self.defaults, fr.etc_keep(mode, str(self.etc)))

    def test_keep_mode(self):
        self.reset("keep")
        e = self.etc
        # a fiókok, a nyelv, a Wi-Fi, a gép kulcsa és a fájlmentés beállítása marad
        self.assertIn("anna", (e / "passwd").read_text())
        self.assertEqual((e / "locale.conf").read_text(), "LANG=hu_HU.UTF-8\n")
        self.assertTrue((e / "NetworkManager/system-connections/Otthon.nmconnection").exists())
        self.assertTrue((e / "ssh/ssh_host_ed25519_key").exists())
        self.assertTrue((e / "sloth-os/snapshots.json").exists())
        # a többi a gyári
        self.assertEqual((e / "systemd/zram-generator.conf").read_text(), "[zram0]\n")
        self.assertFalse((e / "sudoers.d/sloth-admin").exists())
        self.assertTrue((e / "sudoers.d/.keep").exists())
        self.assertFalse((e / "polkit-1/rules.d/49-sloth-admin.rules").exists())
        self.assertEqual((e / "polkit-1/rules.d/50-default.rules").read_text(), "x")
        self.assertFalse((e / "sloth-os/admin-policy.json").exists())
        self.assertFalse((e / "sloth-os/pin").exists())
        wants = e / "systemd/system/multi-user.target.wants"
        self.assertEqual(sorted(os.listdir(wants)), ["a.service"])
        self.assertEqual(os.readlink(wants / "a.service"), "/usr/lib/systemd/system/a.service")
        self.assertEqual(os.readlink(e / "localtime"), "../usr/share/zoneinfo/UTC")
        self.assertEqual(os.stat(e / "NetworkManager/NetworkManager.conf").st_mode & 0o777, 0o644)
        # másodszorra már nincs teendő
        self.assertEqual(self.reset("keep"), (0, 0))

    def test_all_mode_drops_wifi(self):
        self.reset("all")
        e = self.etc
        self.assertFalse((e / "NetworkManager/system-connections/Otthon.nmconnection").exists())
        self.assertTrue((e / "NetworkManager/system-connections").is_dir())
        self.assertEqual(os.listdir(e / "sloth-os"), [])  # a mappa marad: ide kerül az új fiók adata
        self.assertIn("anna", (e / "passwd").read_text())  # a fiókokat a userdel törli, nem ez
        self.assertTrue((e / "ssh/ssh_host_ed25519_key").exists())

    def test_domain_keeps_login_setup(self):
        write(self.etc / "sssd/sssd.conf", "[sssd]\n", 0o600)
        write(self.defaults / "authselect/authselect.conf", "local\n")
        write(self.etc / "authselect/authselect.conf", "sssd\nwith-mkhomedir\n")
        self.reset("keep")
        self.assertTrue((self.etc / "sssd/sssd.conf").exists())
        self.assertEqual((self.etc / "authselect/authselect.conf").read_text(), "sssd\nwith-mkhomedir\n")
        self.reset("all")
        self.assertFalse((self.etc / "sssd").exists())
        self.assertEqual((self.etc / "authselect/authselect.conf").read_text(), "local\n")

    def test_dir_replaced_by_file(self):
        shutil.rmtree(self.etc / "sudoers.d")
        write(self.etc / "sudoers.d", "nem mappa")
        self.reset("keep")
        self.assertTrue((self.etc / "sudoers.d/.keep").exists())


class KargsTest(unittest.TestCase):
    def test_only_added_ones_go(self):
        defaults = {"quiet", "rhgb", "splash", "loglevel=3"}
        current = ["BOOT_IMAGE=(hd0,gpt3)/boot/x", "root=UUID=1", "rootflags=subvol=root", "rw", "ostree=/ostree/1",
                   "rd.luks.uuid=luks-1", "rd.vconsole.keymap=hu", "quiet", "rhgb", "splash", "loglevel=7",
                   "nomodeset", "amdgpu.ppfeaturemask=0xffffffff", "rd.driver.blacklist=nouveau",
                   "modprobe.blacklist=nouveau", "nvidia-drm.modeset=1"]
        self.assertEqual(fr.kargs_to_delete(current, defaults), ["nomodeset", "amdgpu.ppfeaturemask=0xffffffff"])

    def test_default_kargs_from_toml(self):
        d = Path(tempfile.mkdtemp())
        try:
            write(d / "bluebuild-kargs.toml", 'kargs = ["quiet", "rhgb", "loglevel=3"]\n')
            write(d / "rossz.toml", "kargs = [")
            self.assertEqual(fr.default_kargs(d), {"quiet", "rhgb", "loglevel=3"})
        finally:
            shutil.rmtree(d)


class HomeTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.home)

    def test_move_desktop_settings(self):
        write(self.home / ".config/plasma-org.kde.plasma.desktop-appletsrc", "x")
        write(self.home / ".config/sloth-os/welcome-done")
        (self.home / "Régi beállítások").mkdir()
        moved = fr.move_desktop_settings(self.home, "Régi beállítások")
        self.assertEqual(moved.name, "Régi beállítások 2")
        self.assertTrue((moved / "config/plasma-org.kde.plasma.desktop-appletsrc").exists())
        self.assertFalse((self.home / ".config").exists())
        self.assertIsNone(fr.move_desktop_settings(self.home, "Régi beállítások"))

    def test_local_users(self):
        write(self.home / "passwd", "root:x:0:0::/root:/bin/bash\nsddm:x:978:978::/var/lib/sddm:/sbin/nologin\n"
              "anna:x:1000:1000:Anna:/var/home/anna:/bin/bash\nnobody:x:65534:65534::/:/sbin/nologin\n")
        self.assertEqual(fr.local_users(self.home / "passwd"), [("anna", 1000)])

    def test_account_check(self):
        good = {"username": "anna", "fullname": "Kiss Anna", "password_hash": "$6$abc$def"}
        self.assertTrue(fr.check_account(good))
        self.assertFalse(fr.check_account({**good, "username": "Anna"}))
        self.assertFalse(fr.check_account({**good, "fullname": "a:b"}))
        self.assertFalse(fr.check_account({**good, "password_hash": "titok"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
