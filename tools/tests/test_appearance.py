#!/usr/bin/env python3
"""Recognizing the taskbar layout from Plasma's settings (sloth_common.appearance.current_layout)."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
# Only Plasma's D-Bus calls need gi; recognizing the layout does not
if "gi" not in sys.modules:
    try:
        import gi.repository  # noqa: F401
    except ImportError:
        gi = types.ModuleType("gi")
        gi.repository = types.ModuleType("gi.repository")
        gi.repository.Gio = gi.repository.GLib = None
        sys.modules["gi"], sys.modules["gi.repository"] = gi, gi.repository

from sloth_common import appearance  # noqa: E402


def panel(cid, location, plugins):
    """An appletsrc fragment: a panel with the given widgets in this order."""
    ids = [str(cid * 10 + i) for i in range(len(plugins))]
    text = f"[Containments][{cid}]\nplugin=org.kde.panel\nlocation={location}\n\n"
    text += f"[Containments][{cid}][General]\nAppletOrder={';'.join(ids)}\n\n"
    for aid, plugin in zip(ids, plugins):
        text += f"[Containments][{cid}][Applets][{aid}]\nplugin={plugin}\n\n"
    return text


class CurrentLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        appearance.CONFIG_HOME = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def layout(self, *panels):
        (Path(self.tmp.name) / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
            "[Containments][1]\nplugin=org.kde.plasma.folder\n\n" + "".join(panels))
        return appearance.current_layout()

    def test_windows10(self):
        self.assertEqual(self.layout(panel(2, 4, ["org.kde.plasma.kickoff", "org.kde.plasma.icontasks"])),
                         "windows10")

    def test_windows11(self):
        self.assertEqual(self.layout(panel(2, 4, ["org.kde.plasma.panelspacer", "org.kde.plasma.kickoff",
                                                  "org.kde.plasma.icontasks", "org.kde.plasma.panelspacer"])),
                         "windows11")

    def test_mac(self):
        self.assertEqual(self.layout(panel(2, 3, ["org.kde.plasma.kickoff", "org.kde.plasma.appmenu"]),
                                     panel(3, 4, ["org.kde.plasma.icontasks"])), "mac")

    def test_ubuntu(self):
        self.assertEqual(self.layout(panel(2, 3, ["org.kde.plasma.panelspacer", "org.kde.plasma.digitalclock"]),
                                     panel(3, 5, ["org.kde.plasma.icontasks", "org.kde.plasma.kickoff"])),
                         "ubuntu")

    def test_unknown(self):
        self.assertEqual(self.layout(), "")
        self.assertEqual(self.layout(panel(2, 6, ["org.kde.plasma.icontasks"])), "")

    def test_unknown_layout_is_not_applied(self):
        self.assertFalse(appearance.apply_layout("gnome"))
        self.assertFalse(appearance.apply_color_scheme("NotOurs"))


class Accent(unittest.TestCase):
    """The own accent color (kdeglobals [General] AccentColor, as KDE's color settings keep it)."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        appearance.CONFIG_HOME = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def accent(self, value=None):
        if value is not None:
            (Path(self.tmp.name) / "kdeglobals").write_text(f"[General]\nAccentColor={value}\n", encoding="utf-8")
        return appearance.current_accent()

    def test_read(self):
        self.assertEqual(self.accent(), "")
        self.assertEqual(self.accent("224,102,43"), "#e0662b")
        self.assertEqual(self.accent("224,102,43,255"), "#e0662b")
        self.assertEqual(self.accent("#3fa34d"), "#3fa34d")
        self.assertEqual(self.accent("nonsense"), "")

    def test_bad_color_is_not_applied(self):
        for bad in ("red", "#12345", "#1234567", "#gg0000", "1,2,3"):
            self.assertFalse(appearance.apply_accent(bad), bad)

    def test_suggestions_are_lowercase_hex(self):
        # AccentPicker.qml compares them with the current color in lower case
        for c in appearance.ACCENT_COLORS:
            self.assertRegex(c, r"^#[0-9a-f]{6}$")


if __name__ == "__main__":
    os.environ.setdefault("XDG_CONFIG_HOME", tempfile.gettempdir())
    unittest.main()
