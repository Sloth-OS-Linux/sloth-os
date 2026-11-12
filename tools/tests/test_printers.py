#!/usr/bin/env python3
"""Printers and scanners (sloth_center/printers.py): reading lpstat and scanimage. The lpstat text is what CUPS 2.4
in Fedora 44 printed for a printer made with lpadmin (LC_ALL=C). Needs PySide6."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import printers as pr  # noqa: E402

DETAILS = """printer Office_Laser is idle.  enabled since Thu Nov 12 07:34:14 2026
\tForm mounted:
\tContent types: any
\tPrinter types: unknown
\tDescription: Office Laser (2nd floor)
printer Old_Inkjet disabled since Thu Nov 12 07:34:14 2026 -
\tPaused
\tDescription: Old Inkjet
printer Busy now printing Busy-3.  enabled since Thu Nov 12 07:34:14 2026
\tDescription:
"""


class Lpstat(unittest.TestCase):
    def test_parse(self):
        got = pr.parse_lpstat("Office_Laser\nOld_Inkjet\nBusy\nHP_OfficeJet_Pro_9010_series\n", DETAILS)
        self.assertEqual(got, [
            {"name": "Office_Laser", "label": "Office Laser (2nd floor)", "state": "idle"},
            {"name": "Old_Inkjet", "label": "Old Inkjet", "state": "stopped"},
            {"name": "Busy", "label": "Busy", "state": "printing"},
            # found on the network, made by CUPS at the first print
            {"name": "HP_OfficeJet_Pro_9010_series", "label": "HP OfficeJet Pro 9010 series", "state": ""}])

    def test_scanners(self):
        text = "airscan:e0:HP OfficeJet\tHP OfficeJet Pro 9010\nv4l:/dev/video0\tNoname webcam\nnot a line\n"
        self.assertEqual(pr.parse_scanners(text),
                         [{"device": "airscan:e0:HP OfficeJet", "label": "HP OfficeJet Pro 9010"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
