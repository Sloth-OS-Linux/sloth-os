#!/usr/bin/env python3
"""Recognizing WinUI 3 / .NET MAUI programs (sloth_exe/winui.py); no Qt, Wine or Proton needed.

  python3 tools/tests/test_winui.py [program.exe …]   (with files: prints what each one is)
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-exe"))

from sloth_exe import winui  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="sloth-winui-"))


def exe(folder, name, body=b""):
    path = TMP / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + b"\0" * 62 + body)
    return path


class WinUiTest(unittest.TestCase):
    def test_files_next_to_it(self):
        """A normal (not single-file) build: the Windows App SDK's files sit next to the program."""
        program = exe("plain", "App.exe")
        (program.parent / "Microsoft.WinUI.dll").write_bytes(b"MZ")
        self.assertTrue(winui.detect(program))

    def test_single_file_bundle(self):
        """A single-file .NET program names its files in the manifest at its end (PcInfo, 2026-10-27)."""
        manifest = b"\x13Microsoft.WinUI.dll\x2dMicrosoft.WindowsAppRuntime.Bootstrap.dll\x0dPcInfoApp.dll"
        self.assertTrue(winui.detect(exe("bundle", "PcInfo-x64.exe", b"\0" * 4096 + manifest)))

    def test_other_programs(self):
        self.assertFalse(winui.detect(exe("other", "notepad++.exe", b"Avalonia.Win32.dll WebView2Loader.dll")))
        # the marker far from the end (not in a bundle manifest) does not count
        far = b"Microsoft.WinUI.dll" + b"\0" * (winui.TAIL_BYTES + 10)
        self.assertFalse(winui.detect(exe("far", "big.exe", far)))
        self.assertFalse(winui.detect(TMP / "missing" / "nothing.exe"))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            print(f"{arg}: {'WinUI 3' if winui.detect(arg) else 'not WinUI 3'}")
    else:
        unittest.main(verbosity=2)
