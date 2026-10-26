#!/usr/bin/env python3
"""Tests of the shared application management (sloth_common.apps). They run without Qt and Wine, on Linux.

  python3 tools/tests/test_apps.py

In a temporary home folder (HOME, XDG_*) it builds fake Windows environments: a registry,
shortcuts (.lnk), .exe files, programs in the old layout, and Steam files.
"""
import json
import os
import shlex
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# On disk, not in /tmp: that is often tmpfs, where the library (rightly) does not allow Windows programs (SUPPORTED_FS)
_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
_CACHE.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp(prefix="sloth-apps-test-", dir=_CACHE))
os.environ.update(HOME=str(TMP), XDG_DATA_HOME=str(TMP / ".local/share"), XDG_CONFIG_HOME=str(TMP / ".config"),
                  XDG_CACHE_HOME=str(TMP / ".cache"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common.apps import detect, imports, library, menu, packages, recipes, steam, winreg  # noqa: E402

SYSTEM_REG = r'''WINE REGISTRY Version 2
;; All keys relative to \\Machine

#arch=win64

[Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Wine Mono Runtime] 1729000000
"DisplayName"="Wine Mono Runtime"

[Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Battle.net] 1729000001
#time=1db1f0a
"DisplayIcon"="\"C:\\Program Files (x86)\\Battle.net\\Battle.net.exe\",0"
"DisplayName"="Battle.net"
"DisplayVersion"="2.39.0"
"EstimatedSize"=dword:00012345
"InstallLocation"="C:\\Program Files (x86)\\Battle.net"
"Publisher"="Blizzard Entertainment"
"UninstallString"="\"C:\\ProgramData\\Battle.net\\Agent\\Blizzard Uninstaller.exe\" --lang=enUS"
"Binary"=hex:01,02,03,\
  04,05

[Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Microsoft Visual C++ 2019 X64] 1729000002
"DisplayName"="Microsoft Visual C++ 2019 X64 Minimum Runtime"
'''


def make_lnk(target):
    """A minimal Windows shortcut (MS-SHLLINK), LinkInfo + LocalBasePath (ANSI)."""
    header = bytearray(0x4C)
    header[0:4] = b"\x4c\x00\x00\x00"
    struct.pack_into("<I", header, 0x14, 0x02)  # HasLinkInfo
    path = target.encode("cp1252") + b"\x00"
    info_header = 0x1C
    info = bytearray(info_header)
    struct.pack_into("<I", info, 0, info_header + len(path))  # LinkInfoSize
    struct.pack_into("<I", info, 4, info_header)              # LinkInfoHeaderSize
    struct.pack_into("<I", info, 8, 0x01)                     # VolumeIDAndLocalBasePath
    struct.pack_into("<I", info, 0x10, info_header)           # LocalBasePathOffset
    return bytes(header) + bytes(info) + path


def touch(path, size=1):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)
    return path


def fake_battlenet(app):
    """Battle.net's state after installing, in the program's environment."""
    bnet = app.prefix / "drive_c/Program Files (x86)/Battle.net"
    touch(bnet / "Battle.net.exe", 5 * 1024 ** 2)
    touch(bnet / "Battle.net Launcher.exe", 1024 ** 2)
    touch(bnet / "Battle.net Uninstaller.exe")
    touch(bnet / "BlizzardError.exe")
    touch(bnet / "Battle.net.13000/Battle.net.exe")
    touch(bnet / "Battle.net.13000/QtWebEngineProcess.exe")
    (app.prefix / "system.reg").write_text(SYSTEM_REG, encoding="utf-8")
    start = app.prefix / "drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/Battle.net"
    start.mkdir(parents=True)
    (start / "Battle.net.lnk").write_bytes(make_lnk(r"C:\Program Files (x86)\Battle.net\Battle.net Launcher.exe"))
    (start / "Uninstall Battle.net.lnk").write_bytes(
        make_lnk(r"C:\Program Files (x86)\Battle.net\Battle.net Uninstaller.exe"))
    return bnet


class WinRegTest(unittest.TestCase):
    def test_uninstall_entries(self):
        prefix = TMP / "reg-test"
        prefix.mkdir(exist_ok=True)
        (prefix / "system.reg").write_text(SYSTEM_REG, encoding="utf-8")
        entries = winreg.uninstall_entries(prefix)
        self.assertEqual(set(entries), {"wine mono runtime", "battle.net", "microsoft visual c++ 2019 x64"})
        bnet = entries["battle.net"]
        self.assertEqual(bnet["displayname"], "Battle.net")
        self.assertEqual(bnet["publisher"], "Blizzard Entertainment")
        self.assertEqual(bnet["estimatedsize"], 0x12345)
        self.assertEqual(bnet["installlocation"], r"C:\Program Files (x86)\Battle.net")
        self.assertEqual(winreg.exe_from_icon(bnet["displayicon"]), r"C:\Program Files (x86)\Battle.net\Battle.net.exe")
        self.assertNotIn("binary", bnet)

    def test_exe_from_icon(self):
        self.assertEqual(winreg.exe_from_icon(r"C:\X\a.exe,0"), r"C:\X\a.exe")
        self.assertEqual(winreg.exe_from_icon(r'"C:\X Y\a.exe"'), r"C:\X Y\a.exe")
        self.assertIsNone(winreg.exe_from_icon(r"C:\X\a.ico"))
        self.assertIsNone(winreg.exe_from_icon(5))


class DetectTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(detect.display_name("Battle.net-Setup.exe"), "Battle.net")
        self.assertEqual(detect.display_name("setup_firefox-123.4.exe"), "Firefox")
        self.assertTrue(detect.looks_like_installer("Battle.net-Setup.exe"))
        self.assertTrue(detect.looks_like_installer("x.msi"))
        self.assertFalse(detect.looks_like_installer("game.exe"))

    def test_installer_by_contents(self):
        """7-Zip's 7z2605-x64.exe has no installer word in its name, only in its version information
        ("7-Zip Installer"); run as a program, it was installed again and again (2026-10-22)."""
        def exe(name, body):
            path = TMP / name
            path.write_bytes(b"MZ" + b"\x90" * 64 + body + b"\0" * 32)
            return path

        def version(key, value):
            return key.encode("utf-16-le") + b"\0\0" + value.encode("utf-16-le") + b"\0\0"
        self.assertTrue(detect.looks_like_installer(exe("7z2605-x64.exe", version("FileDescription", "7-Zip Installer"))))
        self.assertTrue(detect.looks_like_installer(exe("tool.exe", version("OriginalFilename", "7zipInstall.exe"))))
        self.assertTrue(detect.looks_like_installer(exe("app.exe", b"Nullsoft Install System v3.10")))
        self.assertFalse(detect.looks_like_installer(exe("notepad++.exe", version("FileDescription", "Notepad++"))))
        text = TMP / "readme.exe"
        text.write_bytes(b"Setup notes, not an executable")
        self.assertFalse(detect.looks_like_installer(text))

    def test_parse_lnk(self):
        lnk = TMP / "a.lnk"
        lnk.write_bytes(make_lnk(r"C:\Program Files\X\x.exe"))
        self.assertEqual(detect.parse_lnk(lnk), r"C:\Program Files\X\x.exe")

    def test_battlenet_install(self):
        app = library.create("Battle Net", installer="/tmp/Battle.net-Setup.exe")
        (app.prefix / "drive_c/windows/system32").mkdir(parents=True)
        touch(app.prefix / "drive_c/Program Files (x86)/Common Files/wine-helper.exe")  # it was there before too
        before = detect.baseline(app)
        bnet = fake_battlenet(app)
        found = detect.detect(app, before, fallback_name="Battle Net")
        self.assertEqual(found.name, "Battle.net")
        self.assertEqual(found.publisher, "Blizzard Entertainment")
        self.assertEqual(found.install_dir, bnet)
        self.assertTrue(found.sure)
        checked = [(c.name, c.path.name) for c in found.candidates if c.checked]
        # the shortcut wins, and the same name goes into the Start menu only once
        self.assertEqual(checked, [("Battle.net", "Battle.net Launcher.exe")])
        names = {c.path.name for c in found.candidates}
        self.assertNotIn("Battle.net Uninstaller.exe", names)
        self.assertNotIn("QtWebEngineProcess.exe", names)
        self.assertNotIn("wine-helper.exe", names)

        # after renaming (the recognized name) the same comes out with the old baseline too
        app = library.rename(app, found.name)
        self.assertEqual(app.dir.name, "Battle.net")
        self.assertEqual(app.id, "battle-net")
        again = detect.detect(app, before, fallback_name="Battle.net")
        self.assertEqual([c.path.name for c in again.candidates if c.checked], ["Battle.net Launcher.exe"])
        library.remove(app)

    def test_ea_app_versioned_dir(self):
        """EA app (2026-10-20, VM): the files in a versioned folder, a link next to it; Wine's sample programs are new too."""
        app = library.create("EA app")
        before = detect.baseline(app)
        drive_c = app.prefix / "drive_c"
        for p in ("Internet Explorer/iexplore.exe", "Windows Media Player/wmplayer.exe",
                  "Windows NT/Accessories/wordpad.exe"):
            touch(drive_c / "Program Files" / p)  # Wine creates them while the installer runs
        ea = drive_c / "Program Files/Electronic Arts/EA Desktop"
        ver = ea / "13.809.0.6322/EA Desktop"
        touch(ver / "EADesktop.exe", 30 * 1024 ** 2)
        touch(ver / "compatibility32/EADesktop.exe")
        for helper in ("ErrorReporter.exe", "EAUpdater.exe", "EASteamProxy.exe", "Link2EA.exe"):
            touch(ver / helper, 10 * 1024 ** 2)
        (ea / "EA Desktop").symlink_to("13.809.0.6322/EA Desktop")
        found = detect.detect(app, before, fallback_name="EA app")
        paths = [c.path for c in found.candidates]
        self.assertFalse(any("Internet Explorer" in str(p) or p.name == "wordpad.exe" for p in paths))
        self.assertNotIn("ErrorReporter.exe", [p.name for p in paths])
        checked = [c.path for c in found.candidates if c.checked]
        # through the link, so it stays valid after the EA app updates (a new versioned folder)
        self.assertEqual(checked, [ea / "EA Desktop/EADesktop.exe"])
        library.remove(app)

    def test_no_registry_no_shortcut(self):
        """A portable zip-like installer: there are only .exe files; the one with the best score is ticked."""
        app = library.create("Cool Tool")
        before = detect.baseline(app)
        d = app.prefix / "drive_c/Program Files/Cool Tool"
        touch(d / "CoolTool.exe", 3 * 1024 ** 2)
        touch(d / "updater.exe")
        touch(d / "bin/crashpad_handler.exe")
        touch(d / "helpers/converter.exe")
        found = detect.detect(app, before, fallback_name="Cool Tool")
        self.assertFalse(found.sure)
        self.assertEqual(found.install_dir, d)
        self.assertEqual([c.path.name for c in found.candidates if c.checked], ["CoolTool.exe"])
        self.assertNotIn("updater.exe", [c.path.name for c in found.candidates])
        library.remove(app)


class LibraryTest(unittest.TestCase):
    def test_create_unique(self):
        a = library.create("Foo")
        b = library.create("Foo")
        self.assertNotEqual(a.id, b.id)
        self.assertNotEqual(a.dir, b.dir)
        self.assertEqual(b.dir.name, "Foo (2)")
        self.assertEqual(library.find(b.id), b)
        self.assertTrue(library.remove(a) and library.remove(b))
        self.assertFalse(a.dir.exists())

    def test_remove_refuses_outside(self):
        outside = TMP / "not-a-library" / "X"
        (outside / ".sloth").mkdir(parents=True)
        (outside / ".sloth/app.json").write_text('{"id": "x"}')
        self.assertFalse(library.remove(library.App(outside)))
        self.assertTrue(outside.exists())

    def test_folder_name(self):
        self.assertEqual(library.folder_name("Battle.net"), "Battle.net")
        self.assertEqual(library.folder_name("../.hidden/x"), "-.hidden-x")
        self.assertEqual(library.folder_name(""), "Program")

    def test_windows_paths(self):
        app = library.create("Paths")
        exe = touch(app.prefix / "drive_c/Program Files/Paths/run.exe")
        self.assertEqual(app.host_to_windows(exe), r"C:\Program Files\Paths\run.exe")
        self.assertEqual(app.windows_to_host(r"c:\program files\PATHS\RUN.EXE"), exe)
        library.remove(app)

    def test_menu_and_move(self):
        app = library.create("Mover")
        exe = touch(app.prefix / "drive_c/Program Files/Mover/mover.exe")
        outside = touch(TMP / "Downloads/portable.exe")
        menu.add(app, "Mover", exe)
        menu.add(app, "Portable", outside)
        app.link_files(exe.parent, "Program files")
        targets = {e["name"]: e["target"] for e in menu.entries(app)}
        self.assertEqual(targets["Mover"], "drive_c/Program Files/Mover/mover.exe")
        self.assertEqual(targets["Portable"], str(outside))
        other = TMP / "OtherLibrary"
        moved = library.move(app, other)
        self.assertIsNotNone(moved)
        self.assertEqual(moved.dir.parent, other)
        self.assertFalse(app.dir.exists())
        # the entries stay valid, and so does the link to the files
        for e in menu.entries(moved):
            self.assertTrue((moved.prefix / e["target"]).is_file(), e)
        self.assertTrue((moved.dir / "Program files" / "mover.exe").is_file())
        self.assertEqual(library.find(app.id), moved)
        library.remove(moved)
        self.assertEqual(menu.entries(moved), [])


class WindowsProcessTest(unittest.TestCase):
    def test_windows_exe_after_wrapper_args(self):
        proc = TMP / "proc-cmdline"
        proc.mkdir(exist_ok=True)
        (proc / "cmdline").write_bytes(b"/path/proton\0run\0C:\\Program Files\\Notepad++\\notepad++.exe\0")
        self.assertEqual(library._windows_exe(proc), "notepad++.exe")

    def test_windows_exe_from_process_name(self):
        proc = TMP / "proc-comm"
        proc.mkdir(exist_ok=True)
        (proc / "cmdline").write_bytes(b"/path/wine64\0")
        (proc / "comm").write_text("7zFM.exe\n", encoding="utf-8")
        self.assertEqual(library._windows_exe(proc), "7zfm.exe")

    def test_wine_infrastructure_is_not_an_app(self):
        proc = TMP / "proc-infra"
        proc.mkdir(exist_ok=True)
        (proc / "cmdline").write_bytes(b"/path/wine64\0services.exe\0")
        (proc / "comm").write_text("wine64\n", encoding="utf-8")
        self.assertIsNone(library._windows_exe(proc))


class MigrationTest(unittest.TestCase):
    def test_migrate_legacy(self):
        legacy = library.LEGACY_ROOT / "battle-net"
        exe = touch(legacy / "files/drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe")
        touch(legacy / "icons/battle-net-launcher.png")
        touch(legacy / "naplo/battle-net-launcher.log")
        touch(legacy / "pillanatkep/drive_c/x")
        (legacy / "meta.json").write_text(json.dumps({"name": "Battle.net", "prefix_proton": "UMU-Proton-9.0",
                                                     "launch": {"x": {"good": {"proton": "UMU-Proton-9.0"}}}}))
        shared = library.LEGACY_ROOT / library.SHARED_ID
        touch(shared / "files/drive_c/windows/x")
        (shared / "meta.json").write_text(json.dumps({"name": "Other programs"}))
        download = touch(TMP / "Downloads/tool.exe")
        menu.APPS_DIR.mkdir(parents=True, exist_ok=True)
        # the old .exe handler's entries
        rel = os.path.relpath(exe, legacy / "files")
        (menu.APPS_DIR / "sloth-win-battle-net-battle-net-launcher.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Battle.net\n"
            f"Exec=sloth-exe --launch battle-net {shlex.quote(rel)}\n"
            f"Icon={legacy}/icons/battle-net-launcher.png\nX-Sloth-Program=battle-net\n")
        rel_out = os.path.relpath(download, shared / "files")
        (menu.APPS_DIR / f"sloth-win-{library.SHARED_ID}-tool.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Tool\n"
            f"Exec=sloth-exe --launch {library.SHARED_ID} {shlex.quote(rel_out)}\n"
            f"X-Sloth-Program={library.SHARED_ID}\n")

        # they show up at the old location too (the old Sloth Center / .exe handler finds them the same way)
        self.assertEqual({a.id for a in library.all_apps()} >= {"battle-net", library.SHARED_ID}, True)
        moved = library.migrate_legacy(busy=lambda a: False)
        self.assertEqual({a.id for a in moved}, {"battle-net", library.SHARED_ID})
        self.assertFalse(library.LEGACY_ROOT.exists())

        app = library.find("battle-net")
        self.assertEqual(app.dir, library.DEFAULT_LIBRARY / "Battle.net")
        self.assertFalse(app.legacy)
        self.assertTrue((app.prefix / "drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe").is_file())
        self.assertEqual(app.meta["prefix_proton"], "UMU-Proton-9.0")
        self.assertEqual(app.meta["schema"], library.SCHEMA)
        self.assertTrue((app.snapshot / "drive_c/x").is_file())
        self.assertTrue((app.log_dir / "battle-net-launcher.log").is_file())
        (entry,) = menu.entries(app)
        self.assertTrue((app.prefix / entry["target"]).is_file())
        self.assertEqual(entry["icon"], str(app.icons / "battle-net-launcher.png"))
        self.assertTrue(Path(entry["icon"]).is_file())
        self.assertIn("Icon=", (app.dir / ".directory").read_text())

        shared_app = library.find(library.SHARED_ID)
        (tool,) = menu.entries(shared_app)
        self.assertEqual(tool["target"], str(download))  # a file outside the environment with its full path
        self.assertEqual(library.migrate_legacy(busy=lambda a: False), [])  # the second time there is nothing to do
        library.remove(app)
        library.remove(shared_app)

    def test_busy_stays(self):
        legacy = library.LEGACY_ROOT / "busy-one"
        touch(legacy / "files/drive_c/x.exe")
        (legacy / "meta.json").write_text('{"name": "Busy"}')
        self.assertEqual(library.migrate_legacy(busy=lambda a: True), [])
        self.assertTrue(legacy.is_dir())
        app = library.find("busy-one")
        self.assertTrue(app.legacy)
        self.assertTrue(library.remove(app))


class SteamTest(unittest.TestCase):
    @staticmethod
    def _bvdf(node):
        out = b""
        for k, v in node.items():
            if isinstance(v, dict):
                out += b"\x00" + k.encode() + b"\x00" + SteamTest._bvdf(v) + b"\x08"
            elif isinstance(v, int):
                out += b"\x02" + k.encode() + b"\x00" + struct.pack("<i", v)
            else:
                out += b"\x01" + k.encode() + b"\x00" + v.encode() + b"\x00"
        return out

    def test_shortcuts_link_and_adopt(self):
        root = steam.FLATPAK_ROOT
        (root / "steamapps").mkdir(parents=True)
        appid = 3123456789  # Steam stores it as a signed 32-bit number
        signed = struct.unpack("<i", struct.pack("<I", appid))[0]
        pfx = root / f"steamapps/compatdata/{appid}/pfx"
        exe = touch(pfx / "drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe")
        cfg = root / "userdata/123/config"
        cfg.mkdir(parents=True)
        data = self._bvdf({"shortcuts": {"0": {"appid": signed, "AppName": "Battle.net", "Exe": f'"{exe}"',
                                              "StartDir": f'"{exe.parent}"', "LaunchOptions": ""},
                                        "1": {"appid": 5, "AppName": "Linux game", "Exe": '"/usr/bin/foo"'}}}) + b"\x08"
        (cfg / "shortcuts.vdf").write_bytes(data)
        (root / "config").mkdir(parents=True)
        (root / "config/config.vdf").write_text(
            '"InstallConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n{\n"CompatToolMapping"\n{\n'
            f'"{appid}"\n{{\n"name"\t\t"proton_experimental"\n}}\n}}\n}}\n}}\n}}\n}}\n')

        (sc,) = steam.shortcuts()
        self.assertEqual(sc["appid"], appid)
        self.assertEqual(sc["gameid"], (appid << 32) | 0x02000000)
        self.assertEqual(sc["prefix"], pfx)
        self.assertEqual(sc["proton"], "proton_experimental")
        self.assertTrue(sc["flatpak"])

        (f,) = imports.found({"steam": imports.SOURCES["steam"]})
        self.assertEqual(f.key, f"steam:{appid}")
        self.assertTrue(imports.can_link(f) and imports.can_adopt(f))

        linked = imports.link(f)
        self.assertEqual(linked.kind, "link")
        self.assertEqual(linked.dir.parent, library.RECORDS)  # no empty folder in ~/Applications
        (entry,) = menu.entries(linked)
        self.assertIn(f"steam://rungameid/{sc['gameid']}", Path(entry["desktop"]).read_text())
        self.assertEqual(imports.imported(f.key), linked)
        self.assertEqual(imports.launch_command(linked)[-1], f"steam://rungameid/{sc['gameid']}")
        self.assertEqual(imports.found({"steam": imports.SOURCES["steam"]}), [])  # already taken over
        library.remove(linked)

        adopted = imports.adopt(f, "Program files")
        self.assertIsNotNone(adopted)
        self.assertEqual(adopted.kind, "windows")
        self.assertTrue(exe.is_file())  # Steam's copy is untouched
        (entry,) = menu.entries(adopted)
        self.assertTrue((adopted.prefix / entry["target"]).is_file())
        self.assertEqual(adopted.meta["install_dir"], r"C:\Program Files (x86)\Battle.net")
        library.remove(adopted)


class OtherSourcesTest(unittest.TestCase):
    def test_simple_yaml(self):
        data = imports.simple_yaml(
            "Name: My Bottle\nInstalled_Dependencies:\n- dxvk\n- vkd3d\nExternal_Programs:\n"
            "  abc-1:\n    name: 'Battle.net'\n    path: /x/drive_c/a b.exe\n    removed: false\n"
            "game:\n  exe: \"/y/z.exe\"\n  args: ''\nempty: {}\n")
        self.assertEqual(data["Name"], "My Bottle")
        self.assertEqual(data["External_Programs"]["abc-1"],
                         {"name": "Battle.net", "path": "/x/drive_c/a b.exe", "removed": False})
        self.assertEqual(data["game"], {"exe": "/y/z.exe", "args": ""})

    def test_lutris(self):
        import sqlite3
        data = imports.LUTRIS_DATA[0]
        prefix = TMP / "Games/battlenet"
        exe = touch(prefix / "drive_c/Program Files (x86)/Battle.net/Battle.net Launcher.exe")
        (data / "games").mkdir(parents=True)
        (data / "games/battlenet-123.yml").write_text(
            f"game:\n  exe: {exe}\n  prefix: {prefix}\nwine:\n  version: lutris-GE\n", encoding="utf-8")
        con = sqlite3.connect(data / "pga.db")
        con.execute("CREATE TABLE games (id INTEGER, name TEXT, runner TEXT, installed INTEGER, configpath TEXT)")
        con.execute("INSERT INTO games VALUES (7, 'Battle.net', 'wine', 1, 'battlenet-123')")
        con.execute("INSERT INTO games VALUES (8, 'Native game', 'linux', 1, 'native-1')")
        con.commit()
        con.close()
        (f,) = imports.found({"lutris": imports.SOURCES["lutris"]})
        self.assertEqual((f.key, f.name, f.prefix), ("lutris:7", "Battle.net", prefix))
        self.assertEqual(f.command, ["lutris", "lutris:rungameid/7"])
        self.assertTrue(imports.can_adopt(f))

    def test_bottles(self):
        bottle = imports.BOTTLES_ROOTS[0] / "Gaming"
        exe = touch(bottle / "drive_c/Program Files/Tool/tool.exe")
        bottle.mkdir(parents=True, exist_ok=True)
        (bottle / "bottle.yml").write_text(
            "Name: Gaming\nExternal_Programs:\n  1f2e:\n    name: Tool\n    path: " + str(exe) + "\n"
            "  dead:\n    name: Old\n    path: /nowhere/old.exe\n    removed: true\n", encoding="utf-8")
        (f,) = imports.found({"bottles": imports.SOURCES["bottles"]})
        self.assertEqual((f.key, f.name), ("bottles:Gaming/1f2e", "Tool"))
        self.assertEqual(f.command[-5:], ["run", "-b", "Gaming", "-p", "Tool"])
        self.assertIn("flatpak", f.command)

    def test_wine(self):
        prefix = imports.WINE_PREFIX
        touch(prefix / "drive_c/Program Files/Office/office.exe", 2 * 1024 ** 2)
        start = prefix / "drive_c/users/someone/AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
        start.mkdir(parents=True)
        (start / "Office.lnk").write_bytes(make_lnk(r"C:\Program Files\Office\office.exe"))
        (f,) = imports.found({"wine": imports.SOURCES["wine"]})
        self.assertEqual((f.name, f.command), ("Office", None))
        self.assertFalse(imports.can_link(f))
        self.assertIsNone(imports.link(f))
        app = imports.adopt(f, "Program files")
        self.assertIsNotNone(app)
        self.assertTrue((prefix / "drive_c/Program Files/Office/office.exe").is_file())  # the original stays
        (entry,) = menu.entries(app)
        self.assertEqual(entry["target"], "drive_c/Program Files/Office/office.exe")
        library.remove(app)


class PackagesTest(unittest.TestCase):
    def test_kind_of(self):
        d = TMP / "pkgs"
        d.mkdir(exist_ok=True)
        cases = {
            "Krita-5.2.6-x86_64.AppImage": b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\0" * 60,
            "noext-appimage": b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\0" * 60,
            "signal_7.1_amd64.deb": b"!<arch>\ndebian-binary   " + b"\0" * 40,
            "tool-1.0.x86_64.rpm": b"\xed\xab\xee\xdb" + b"\0" * 60,
            "Installer.pkg": b"xar!" + b"\0" * 60,
            "App.dmg": b"\0" * 2000 + b"koly" + b"\0" * 508,
            "Thing.app.zip": b"PK\x03\x04" + b"\0" * 60,
            "run.command": b"#!/bin/sh\n",
            "plain.zip": b"PK\x03\x04" + b"\0" * 60,
        }
        want = {"Krita-5.2.6-x86_64.AppImage": "appimage", "noext-appimage": "appimage", "signal_7.1_amd64.deb": "deb",
                "tool-1.0.x86_64.rpm": "rpm", "Installer.pkg": "mac", "App.dmg": "mac", "Thing.app.zip": "mac",
                "run.command": "mac-script", "plain.zip": None}
        for name, data in cases.items():
            (d / name).write_bytes(data)
            self.assertEqual(packages.kind_of(d / name), want[name], name)

    def test_names(self):
        self.assertEqual(packages.display_name("Krita-5.2.6-x86_64.AppImage"), "Krita")
        self.assertEqual(packages.display_name("signal-desktop_7.1.0_amd64.deb"), "Signal Desktop")
        self.assertEqual(packages.display_name("Obsidian-1.6.7.AppImage"), "Obsidian")

    def test_box_steps_and_output(self):
        deb = touch(TMP / "Downloads/tool_1.0_amd64.deb")
        steps = packages.box_steps("deb", deb, box_exists=False)
        self.assertEqual([k for k, _ in steps], ["box.create", "box.first_start", "box.install"])
        self.assertIn("docker.io/library/ubuntu:24.04", steps[0][1])
        self.assertIn(str(deb), steps[-1][1][-1])
        self.assertIn('grep -q "^Exec=.*sloth-exe" "$f"', steps[-1][1][-1])
        self.assertIn('grep -q "^Exec=.*distrobox-enter" "$exported"', steps[-1][1][-1])
        self.assertIn('Exported launcher is missing or unusable', steps[-1][1][-1])
        self.assertEqual([k for k, _ in packages.box_steps("rpm", deb, box_exists=True)], ["box.install"])
        self.assertTrue(packages.box_path("/tmp/x.deb").startswith("/run/host/"))
        name, apps = packages.parse_box_output(["noise", "SLOTH-NAME:tool", "SLOTH-APP:org.tool.App|Tool"])
        self.assertEqual((name, apps), ("tool", [{"id": "org.tool.App", "name": "Tool"}]))
        app = packages.record_box_install("deb", deb, name, apps)
        self.assertEqual((app.kind, app.name), ("box", "Tool"))
        self.assertEqual(app.dir.parent, library.RECORDS)  # no empty folder in the visible library
        desktop = packages.box_desktop_files(app)[0]
        self.assertTrue(desktop.name.startswith("sloth-ubuntu-"))
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text("[Desktop Entry]\nExec=/usr/bin/distrobox-enter -n sloth-ubuntu -- tool\n", encoding="utf-8")
        self.assertEqual(packages.box_launch_command(app), ["kioclient", "exec", str(desktop)])
        desktop.write_text("[Desktop Entry]\nExec=/usr/bin/distrobox-enter -n sloth-ubuntu -- sloth-exe --launch tool\n",
                           encoding="utf-8")
        self.assertIsNone(packages.box_launch_command(app))
        library.remove(app)

    def test_install_appimage(self):
        """A fake AppImage that, like a real one, extracts the .desktop file and the icon."""
        src = TMP / "Downloads/Coolapp-2.0-x86_64.AppImage"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = --appimage-extract ]; then\n"
            "  mkdir -p squashfs-root/usr/share/icons\n"
            "  printf '[Desktop Entry]\\nName=Cool App\\nIcon=cool\\nCategories=Graphics;\\n' > squashfs-root/cool.desktop\n"
            "  printf '\\211PNG fake' > squashfs-root/usr/share/icons/cool.png\n"
            "  ln -sf usr/share/icons/cool.png squashfs-root/.DirIcon\n"
            "  exit 0\nfi\necho run\n", encoding="utf-8")
        src.chmod(0o644)  # downloaded files are not executable
        app = packages.install_appimage(src)
        self.assertIsNotNone(app)
        self.assertEqual((app.kind, app.name, app.dir.name), ("appimage", "Cool App", "Cool App"))
        path = packages.appimage_path(app)
        self.assertTrue(path.is_file() and path.stat().st_mode & 0o111)
        self.assertTrue(src.is_file())  # the downloaded file stays
        (entry,) = menu.entries(app)
        text = Path(entry["desktop"]).read_text()
        self.assertIn(f"Exec=sloth-exe --run {app.id} %U", text)
        self.assertIn("Categories=Graphics;", text)
        self.assertTrue(Path(entry["icon"]).is_file())
        moved = library.move(app, TMP / "Elsewhere")
        self.assertTrue(packages.appimage_path(moved).is_file())
        (entry,) = menu.entries(moved)
        self.assertTrue(Path(entry["icon"]).is_file())  # the icon's path follows too
        library.remove(moved)


class RecipesTest(unittest.TestCase):
    BUNDLED = REPO / "files/system/usr/share/sloth-os/recipes.json"

    def setUp(self):
        recipes._cache = None
        self.orig = recipes.SYSTEM, recipes.CACHE
        recipes.SYSTEM, recipes.CACHE = self.BUNDLED, TMP / "no-cache/recipes.json"

    def tearDown(self):
        recipes.SYSTEM, recipes.CACHE = self.orig
        recipes._cache = None

    def test_bundled_valid(self):
        data = json.loads(self.BUNDLED.read_text(encoding="utf-8"))
        self.assertEqual(len(recipes.load()), len(data["recipes"]))  # all valid

    def test_validate_rejects(self):
        good = {"id": "x", "name": "X", "match": {"exe": ["x.exe"]}}
        self.assertTrue(recipes.validate(good))
        bad = [
            {**good, "verbs": ["rm -rf"]},
            {**good, "env": ["LD_PRELOAD"]},
            {**good, "args": ["--load-extension=evil"]},
            {**good, "dll_overrides": ["d3d11=n"]},          # loading a native DLL cannot be requested
            {**good, "match": {"dirs": ["/etc"]}},
            {**good, "match": {"dirs": ["../../home"]}},
            {**good, "stubs": {"x.exe": "/usr/bin/sh"}},
            {**good, "stubs": {"x.exe": "../../../x.exe"}},
            {**good, "command": "anything"},                  # unknown field
            {**good, "id": "Bad Id"},
            {**good, "per_exe": {"x.exe": {"env": ["PATH"]}}},
            {"id": "y", "match": {}},
        ]
        for r in bad:
            self.assertFalse(recipes.validate(r), r)
        # the bad one drops out, the good one stays
        f = TMP / "recipes-mixed.json"
        f.write_text(json.dumps({"version": 1, "updated": "2099-01-01", "recipes": [good] + bad}))
        self.assertEqual([r["id"] for r in recipes.load([f])], ["x"])

    def test_newer_download_wins(self):
        newer = TMP / "no-cache/recipes.json"
        newer.parent.mkdir(parents=True, exist_ok=True)
        newer.write_text(json.dumps({"version": 1, "updated": "2099-01-01",
                                     "recipes": [{"id": "only", "match": {"exe": ["only.exe"]}}]}))
        self.assertEqual([r["id"] for r in recipes.load()], ["only"])
        newer.unlink()

    def test_stubs_and_settings(self):
        app = library.create("Recipe test")
        bnet = app.prefix / "drive_c/Program Files (x86)/Battle.net"
        touch(bnet / "Battle.net.exe")
        launcher = touch(bnet / "Battle.net Launcher.exe")
        self.assertEqual(recipes.stub_target(launcher), bnet / "Battle.net.exe")
        self.assertIn("locationapi=d", recipes.settings(app.prefix, launcher)["dll_overrides"])
        epic = app.prefix / "drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries"
        self.assertEqual(recipes.stub_target(epic / "Win32/EpicGamesLauncher.exe"), epic / "Win64/EpicGamesLauncher.exe")
        gog = touch(app.prefix / "drive_c/Program Files (x86)/GOG Galaxy/GalaxyClient.exe")
        s = recipes.settings(app.prefix, gog)
        self.assertEqual(s["args"], ["/runWithoutUpdating", "/deelevated"])
        self.assertEqual(s["verbs"], ["vcrun2022", "dotnet48"])
        self.assertEqual(recipes.settings(app.prefix, touch(TMP / "Downloads/other.exe"))["args"], [])
        library.remove(app)

    def test_detection_uses_recipes(self):
        app = library.create("Battle Net R")
        before = detect.baseline(app)
        fake_battlenet(app)
        touch(app.prefix / "drive_c/Program Files (x86)/Battle.net/Agent.exe", 9 * 1024 ** 2)
        found = detect.detect(app, before, fallback_name="Battle Net")
        names = [c.path.name for c in found.candidates]
        self.assertNotIn("Agent.exe", names)                # dropped by the recipe
        self.assertEqual(names[0], "Battle.net Launcher.exe")  # the recipe's launcher first
        library.remove(app)


def make_elf(sections):
    """A minimal 64-bit ELF with the given sections ({name: contents}), modelled on AppImages."""
    names = b"\0" + b"".join(n.encode() + b"\0" for n in sections) + b".shstrtab\0"
    body, offsets = b"", []
    for data in list(sections.values()) + [names]:
        offsets.append(64 + len(body))
        body += data
    shoff = 64 + len(body)
    head = bytearray(64)
    head[:16] = b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\0" * 5
    struct.pack_into("<Q", head, 0x28, shoff)
    struct.pack_into("<HHH", head, 0x3A, 64, len(sections) + 2, len(sections) + 1)
    table = b"\0" * 64  # the first section is empty
    name_off = 1
    for (name, data), off in zip(list(sections.items()) + [(".shstrtab", names)], offsets):
        table += struct.pack("<IIQQQQ", name_off, 1, 0, 0, off, len(data)) + b"\0" * 24  # 64-byte header
        name_off += len(name) + 1
    return bytes(head) + body + table


class AppImageUpdateTest(unittest.TestCase):
    INFO = "gh-releases-zsync|someone|coolapp|latest|Coolapp-*x86_64.AppImage.zsync"

    def test_update_info(self):
        path = TMP / "elf.AppImage"
        path.write_bytes(make_elf({".text": b"\x90" * 32, ".upd_info": self.INFO.encode() + b"\0" * 100}))
        self.assertEqual(packages.kind_of(path), "appimage")
        self.assertEqual(packages.update_info(path), self.INFO)
        path.write_bytes(make_elf({".text": b"\x90" * 32}))
        self.assertEqual(packages.update_info(path), "")

    def test_update_appimage(self):
        import hashlib
        app = library.create("Updatable", kind="appimage", file="Coolapp.AppImage", update_info=self.INFO)
        app.dir.mkdir(parents=True, exist_ok=True)
        old = app.dir / "Coolapp.AppImage"
        old.write_bytes(b"old version")
        new = b"new version"
        orig = (packages._get, packages.zsync_url, packages.metered)
        packages.zsync_url = lambda info: "https://example.org/Coolapp-2.0-x86_64.AppImage.zsync"
        packages.metered = lambda: False
        sha = {"value": hashlib.sha1(new).hexdigest()}

        def fake_get(url, limit=None):
            if url.endswith(".zsync"):
                return (f"zsync: 0.6.2\nFilename: Coolapp-2.0-x86_64.AppImage\nURL: Coolapp-2.0-x86_64.AppImage\n"
                        f"SHA-1: {sha['value']}\nLength: {len(new)}\n\nbinary").encode()
            self.assertEqual(url, "https://example.org/Coolapp-2.0-x86_64.AppImage")
            return new
        packages._get = fake_get
        try:
            self.assertEqual(packages.update_appimage(app), "updated")
            self.assertEqual(old.read_bytes(), new)
            self.assertTrue(old.stat().st_mode & 0o111)
            self.assertEqual(packages.update_appimage(app), "current")
            sha["value"] = "0" * 40  # corrupt download: the old one stays
            self.assertEqual(packages.update_appimage(app), "skipped")
            self.assertEqual(old.read_bytes(), new)
            self.assertEqual(packages.update_appimages(), [])
        finally:
            packages._get, packages.zsync_url, packages.metered = orig
            library.remove(app)

    def test_flathub_match(self):
        import io
        import urllib.request
        orig = urllib.request.urlopen
        hits = {"hits": [{"app_id": "org.other.Thing", "name": "Other"},
                         {"app_id": "org.signal.Signal", "name": "Signal Desktop", "summary": "Private messenger"}]}
        urllib.request.urlopen = lambda req, timeout=0: io.BytesIO(json.dumps(hits).encode())
        try:
            self.assertEqual(packages.flathub_match("signal-desktop")["id"], "org.signal.Signal")
            self.assertIsNone(packages.flathub_match("Something Else"))
            self.assertIsNone(packages.flathub_match("ab"))
        finally:
            urllib.request.urlopen = orig


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
