#!/usr/bin/env python3
"""Network folders (sloth_center.netfolders): reading what the user typed, adding to and removing from KDE's side
panel without touching the rest of the file, and the computers Avahi finds."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
# Only the Qt part of the module needs PySide6; the logic is tested without it
try:
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: (lambda f: f)
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import netfolders as nf  # noqa: E402

PLACES = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel>
<xbel xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks" xmlns:kdepriv="http://www.kde.org/kdepriv" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">
 <info>
  <metadata owner="http://www.kde.org">
   <kde_places_version>4</kde_places_version>
  </metadata>
 </info>
 <bookmark href="file:///home/anna">
  <title>Home</title>
  <info>
   <metadata owner="http://freedesktop.org">
    <bookmark:icon name="user-home"/>
   </metadata>
   <metadata owner="http://www.kde.org">
    <ID>1792678317/0</ID>
    <isSystemItem>true</isSystemItem>
   </metadata>
  </info>
 </bookmark>
 <bookmark href="remote:/">
  <title>Network</title>
 </bookmark>
</xbel>
"""


class ParseAddress(unittest.TestCase):
    def test_the_same_folder_written_many_ways(self):
        for text in (r"\\NAS\Photos", "//NAS/Photos", "NAS/Photos", "smb://NAS/Photos", "  NAS/Photos/  "):
            self.assertEqual(nf.parse_address(text), "smb://NAS/Photos", text)

    def test_server_only_spaces_and_other_schemes(self):
        self.assertEqual(nf.parse_address(r"\\nas.local"), "smb://nas.local/")
        self.assertEqual(nf.parse_address(r"\\nas\My Photos\2026"), "smb://nas/My%20Photos/2026")
        self.assertEqual(nf.parse_address("nfs://192.168.1.5/export/media"), "nfs://192.168.1.5/export/media")
        self.assertEqual(nf.parse_address("SFTP://pi/home"), "sftp://pi/home")

    def test_not_an_address(self):
        for text in ("", "   ", "http://nas/photos", "file:///etc", r"\\", "my nas/photos"):
            self.assertEqual(nf.parse_address(text), "", text)

    def test_default_name(self):
        self.assertEqual(nf.default_name("smb://nas/My%20Photos"), "My Photos")
        self.assertEqual(nf.default_name("smb://nas.local/"), "nas.local")


class Places(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "user-places.xbel"
        self.path.write_text(PLACES, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_lists_and_removes_leaving_the_rest(self):
        self.assertEqual(nf.folders(self.path), [])
        nf.add("smb://nas/Photos", "Photos & videos", self.path)
        nf.add("smb://nas/Photos", "again", self.path)   # already there: not twice
        self.assertEqual(nf.folders(self.path), [{"name": "Photos & videos", "url": "smb://nas/Photos"}])
        root = ElementTree.parse(self.path).getroot()     # still a valid file KDE can read
        bm = [b for b in root.iter("bookmark") if b.get("href") == "smb://nas/Photos"][0]
        icon = bm.find(".//{http://www.freedesktop.org/standards/desktop-bookmarks}icon")
        self.assertEqual(icon.get("name"), "folder-network")
        nf.remove("smb://nas/Photos", self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), PLACES)

    def test_a_missing_file_gets_a_new_one(self):
        self.path.unlink()
        nf.add("nfs://server/export", "", self.path)
        self.assertEqual(nf.folders(self.path), [{"name": "export", "url": "nfs://server/export"}])
        nf.remove("smb://other/", self.path)   # nothing to remove: nothing changes
        self.assertEqual(len(nf.folders(self.path)), 1)

    def test_a_broken_file_is_not_overwritten(self):
        self.path.write_text("garbage", encoding="utf-8")
        self.assertEqual(nf.folders(self.path), [])
        with self.assertRaises(ValueError):
            nf.add("smb://nas/x", "x", self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "garbage")


class Avahi(unittest.TestCase):
    def test_parse(self):
        out = ("+;enp8s0;IPv4;Big\\032NAS;_smb._tcp;local\n"
               "=;enp8s0;IPv4;Big\\032NAS;_smb._tcp;local;bignas.local;192.168.1.37;445;\n"
               "=;enp8s0;IPv6;Big\\032NAS;_smb._tcp;local;bignas.local;fe80::1;445;\n"
               "=;wlan0;IPv4;anna-pc;_smb._tcp;local;anna-pc.local;192.168.1.20;445;\n")
        self.assertEqual(nf.parse_avahi(out), [{"name": "anna-pc", "url": "smb://anna-pc.local/"},
                                               {"name": "Big NAS", "url": "smb://bignas.local/"}])
        self.assertEqual(nf.parse_avahi(""), [])


if __name__ == "__main__":
    unittest.main()
