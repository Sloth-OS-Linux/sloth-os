#!/usr/bin/env python3
"""Sloth Center's sidebar search (sloth_center/search.py): what a page can be found by."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
os.environ["LANGUAGE"] = "hu"  # the translated texts are searched too
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import search  # noqa: E402


class Search(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(search.normalize("Wi-Fi and network"), "wifiandnetwork")
        self.assertIn(search.normalize("wifi"), search.normalize("Wi-Fi és hálózat"))
        self.assertEqual(search.normalize("Night Light"), search.normalize("nightlight"))

    def test_a_page_by_its_texts(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "X.qml").write_text('Label { text: L.t("Change the password") }\n'
                                        'Label { text: L.tf("{n} updates", {n: 3}) }\n'
                                        'Label { text: L.t("Say \\"hi\\"") }\n', encoding="utf-8")
            text = search.page_text("X.qml", d)
        self.assertIn(search.normalize("password"), text)
        self.assertIn("updates", text)          # the placeholder is left out
        self.assertNotIn("{n}", text)
        self.assertIn("sayhi", text)

    def test_the_real_pages(self):
        accounts = search.page_text("AccountsPage.qml")
        self.assertIn("password", accounts)
        self.assertEqual(search.page_text("NoSuchPage.qml"), "")


if __name__ == "__main__":
    unittest.main()
