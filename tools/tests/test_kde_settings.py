#!/usr/bin/env python3
"""One settings app: KDE's settings pages in Sloth Center (sloth_center/kde_settings.py) and `systemsettings` →
Sloth Center (/usr/libexec/sloth-os/systemsettings-wrapper). Needs PySide6. The category files are shortened copies
of Plasma 6.8's /usr/share/systemsettings/categories."""
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import kde_settings as ks  # noqa: E402

WRAPPER = REPO / "files/system/usr/libexec/sloth-os/systemsettings-wrapper"

CATS = {
    "settings-hardware-input.desktop": "X-KDE-System-Settings-Category=input-devices\n"
                                       "X-KDE-System-Settings-Parent-Category=\nX-KDE-Weight=10\n"
                                       "Icon=preferences-desktop-mouse\nName=Input & Output\n"
                                       "Name[hu]=Bevitel és kivitel\nName[pt_BR]=Entrada e saída\n",
    "settings-hardware-keyboard.desktop": "X-KDE-System-Settings-Category=keyboard\n"
                                          "X-KDE-System-Settings-Parent-Category=input-devices\nX-KDE-Weight=20\n"
                                          "Name=Keyboard\nName[hu]=Billentyűzet\n",
    "settings-appearance.desktop": "X-KDE-System-Settings-Category=appearance\n"
                                   "X-KDE-System-Settings-Parent-Category=\nX-KDE-Weight=40\n"
                                   "Icon=preferences-desktop-theme\nName=Appearance & Style\n",
    "settings-appearance-font.desktop": "X-KDE-System-Settings-Category=font\n"
                                        "X-KDE-System-Settings-Parent-Category=appearance\nName=Text & Fonts\n",
    "settings-root-category.desktop": "X-KDE-System-Settings-Category=rootcategory\nName=Root\n",
}


class Categories(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for name, body in CATS.items():
            Path(self.tmp.name, name).write_text("[Desktop Entry]\n" + body, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_names_in_the_language(self):
        cats = ks.categories("hu", self.tmp.name)
        self.assertEqual(cats["input-devices"]["name"], "Bevitel és kivitel")
        self.assertEqual(cats["appearance"]["name"], "Appearance & Style")      # no Hungarian: English
        self.assertEqual(ks.categories("pt_BR", self.tmp.name)["input-devices"]["name"], "Entrada e saída")
        self.assertEqual(ks.categories("pt", self.tmp.name)["input-devices"]["name"], "Input & Output")
        self.assertNotIn("rootcategory", cats)

    def test_groups(self):
        cats = ks.categories("en", self.tmp.name)
        pages = [{"id": "kcm_fonts", "name": "Fonts", "category": "font"},
                 {"id": "kcm_mouse", "name": "Mouse", "category": "input-devices"},
                 {"id": "kcm_keyboard", "name": "Keyboard", "category": "keyboard"},
                 {"id": "kcm_bluetooth", "name": "Bluetooth", "category": "input-devices"},   # covered
                 {"id": "kcm_landingpage", "name": "Quick Settings", "category": ""},     # hidden
                 {"id": "kcm_odd", "name": "Odd", "category": "nowhere"}]
        got = ks.group(pages, cats)
        self.assertEqual([g["id"] for g in got], ["input-devices", "appearance", ""])
        self.assertEqual([p["id"] for p in got[0]["pages"]], ["kcm_bluetooth", "kcm_keyboard", "kcm_mouse"])
        # a page Sloth Center covers (Drivers and hardware → Bluetooth) is shown only when searching
        self.assertEqual([p["id"] for p in got[0]["pages"] if p["covered"]], ["kcm_bluetooth"])
        self.assertEqual([p["id"] for p in got[1]["pages"]], ["kcm_fonts"])
        self.assertEqual([p["id"] for p in got[2]["pages"]], ["kcm_odd"])


class OpenPage(unittest.TestCase):
    def test_embedded_or_own_window(self):
        ctl = ks.KdeSettingsController()
        got = []
        ctl.openRequested.connect(lambda p, a: got.append((p, a)))
        with mock.patch.object(ks, "embeddable", return_value=True):
            self.assertTrue(ks.open_page("kcm_mouse"))
        self.assertEqual(got, [("kcm_mouse", "")])
        with mock.patch.object(ks, "embeddable", return_value=False), \
                mock.patch.object(ks.shutil, "which", return_value="/usr/bin/kcmshell6"), \
                mock.patch.object(ks.subprocess, "Popen") as popen:
            self.assertTrue(ks.open_page("kcm_networkmanagement"))
        popen.assert_called_once()
        self.assertEqual(popen.call_args[0][0], ["/usr/bin/kcmshell6", "kcm_networkmanagement"])
        self.assertEqual(len(got), 1)


class Wrapper(unittest.TestCase):
    """Where `systemsettings <args>` goes."""

    def route(self, args, qml=(), widget=(), host=True, center=True):
        kcms = "/usr/lib64/qt6/plugins/plasma/kcms"
        present = {f"{kcms}/systemsettings/{p}.so" for p in qml} | {f"{kcms}/systemsettings_qwidgets/{p}.so"
                                                                     for p in widget}
        if host:
            present.add("/usr/lib64/qt6/qml/org/slothos/kcmhost/libkcmhost.so")
        calls = []

        def execv(path, argv):
            calls.append(argv)
            raise SystemExit(0)

        def which(name):
            return {"sloth-center": "/usr/bin/sloth-center" if center else None,
                    "kcmshell6": "/usr/bin/kcmshell6"}.get(name)

        with mock.patch.object(os, "execv", execv), mock.patch("shutil.which", which), \
                mock.patch("os.path.exists", lambda p: p in present), \
                mock.patch.object(sys, "argv", ["systemsettings"] + args):
            with self.assertRaises(SystemExit):
                runpy.run_path(str(WRAPPER), run_name="__main__")
        return calls[0]

    def test_routes(self):
        real = "/usr/libexec/sloth-os/systemsettings.real"
        self.assertEqual(self.route([]), ["/usr/bin/sloth-center", "--page", "kde"])
        self.assertEqual(self.route(["kcm_mouse"], qml=["kcm_mouse"]), ["/usr/bin/sloth-center", "--kcm", "kcm_mouse"])
        self.assertEqual(self.route(["kcm_users", "--args", "bob"], qml=["kcm_users"]),
                         ["/usr/bin/sloth-center", "--kcm", "kcm_users", "--kcm-args", "bob"])
        self.assertEqual(self.route(["kcm_proxy"], widget=["kcm_proxy"]), ["/usr/bin/kcmshell6", "kcm_proxy"])
        self.assertEqual(self.route(["kcm_unknown"]), [real, "kcm_unknown"])
        self.assertEqual(self.route(["--help"]), [real, "--help"])
        # without the module or without Sloth Center: the real System Settings, unchanged
        self.assertEqual(self.route(["kcm_mouse"], qml=["kcm_mouse"], host=False), [real, "kcm_mouse"])
        self.assertEqual(self.route([], center=False), [real])


if __name__ == "__main__":
    unittest.main()
