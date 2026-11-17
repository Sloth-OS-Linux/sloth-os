#!/usr/bin/env python3
"""The "I can't open this file" helper (sloth_center/open_helper.py) and its Start menu entry. The window and the
GIO lookups were tried in the image (an app that opens the type wins; a Word document is not given to Ark through
its zip parent type; the stand-in installer's app opens the file)."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import open_helper as oh  # noqa: E402

ENTRY = REPO / "files/system/usr/share/applications/org.slothos.open.desktop"


class SuggestionTest(unittest.TestCase):
    def test_common_files_get_the_right_app(self):
        cases = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "org.libreoffice.LibreOffice",
            "application/vnd.ms-excel": "org.libreoffice.LibreOffice",
            "application/pdf": "org.kde.okular",
            "image/jpeg": "org.kde.gwenview",
            "image/vnd.adobe.photoshop": "org.gimp.GIMP",
            "video/mp4": "org.videolan.VLC",
            "audio/mpeg": "org.videolan.VLC",
            "application/epub+zip": "com.github.johnfactotum.Foliate",
        }
        for mime, app in cases.items():
            self.assertEqual(oh.suggestion(mime)[0], app, mime)

    def test_unknown_type_has_no_suggestion(self):
        self.assertIsNone(oh.suggestion("application/vnd.sqlite3"))
        self.assertIsNone(oh.suggestion(""))

    def test_each_type_once(self):
        self.assertEqual(len(oh.ALL_TYPES), len(set(oh.ALL_TYPES)))

    def test_entry_lists_exactly_the_suggested_types(self):
        text = ENTRY.read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if ln.startswith("MimeType="))
        self.assertEqual(line[len("MimeType="):].rstrip(";").split(";"), list(oh.ALL_TYPES))
        self.assertIn("Exec=sloth-open %f", text)
        self.assertIn("NoDisplay=true", text)


if __name__ == "__main__":
    unittest.main()
