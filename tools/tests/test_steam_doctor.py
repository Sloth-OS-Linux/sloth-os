#!/usr/bin/env python3
"""What's wrong with the game? (sloth_common/steam_doctor.py): a Steam game that closes right after starting, the fixes
one after the other in Steam's own files (launch options, compatibility tool), and Undo. A fake Steam folder."""
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import steam_doctor as sd  # noqa: E402
from sloth_common.apps import steam  # noqa: E402

APPID = "1145360"


def fake_steam(tmp, options="", tool=None, proton=True):
    root = Path(tmp, "Steam")
    (root / "steamapps").mkdir(parents=True)
    if proton:
        (root / "steamapps/compatdata" / APPID).mkdir(parents=True)
    local = root / "userdata/1234/config/localconfig.vdf"
    local.parent.mkdir(parents=True)
    apps = {APPID: {"LaunchOptions": options}} if options is not None else {}
    local.write_text(steam.vdf_dump({"UserLocalConfigStore": {"Software": {"Valve": {"Steam": {
        "apps": {**apps, "570": {"LaunchOptions": "-novid"}}}}}}}) + "\n")
    mapping = {"0": {"name": "proton_experimental", "config": "", "priority": "75"}}
    if tool:
        mapping[APPID] = tool
    (root / "config").mkdir()
    (root / "config/config.vdf").write_text(steam.vdf_dump({"InstallConfigStore": {"Software": {"Valve": {"Steam": {
        "CompatToolMapping": mapping}}}}}) + "\n")
    return root, local


class Runs(unittest.TestCase):
    def test_quick_close_is_a_failure_a_long_run_after_a_fix_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            self.assertEqual(sd.record_run(APPID, 600, state), "")        # a normal game: nothing noted
            self.assertEqual(sd.load(state), {})
            self.assertEqual(sd.record_run(APPID, 4, state), "failed")
            self.assertEqual(sd.record_run(APPID, 6, state), "failed")
            s = sd.summary(APPID, path=state)
            self.assertEqual((s["failures"], s["lastSeconds"], s["status"], s["changed"]), (2, 6, "failing", False))
            self.assertEqual(sd.record_run(APPID, 45, state), "")         # in between: nothing to say
            # a long run without any fix of ours: the quick closes were something else, the game is forgotten
            self.assertEqual(sd.record_run(APPID, 300, state), "worked")
            self.assertIsNone(sd.summary(APPID, path=state))

    def test_a_long_run_after_a_fix_keeps_the_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp)
            sd.record_run(APPID, 3, state)
            sd.try_next(root, local, APPID, path=state)
            self.assertEqual(sd.record_run(APPID, 300, state), "worked")
            self.assertEqual(sd.summary(APPID, root, state)["status"], "works")

    def test_forget_only_without_a_fix(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            sd.record_run(APPID, 3, state)
            sd.forget(APPID, state)
            self.assertIsNone(sd.summary(APPID, path=state))


class Fixes(unittest.TestCase):
    def test_the_ladder_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp, options="gamemoderun %command% -skipintro")
            sd.record_run(APPID, 3, state)
            # 1. without fsync: our variables go first, the user's words and our per-game setting stay
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "nofsync")
            options, tool = sd.read_settings(root, local, APPID)
            self.assertEqual(options, "PROTON_NO_FSYNC=1 PROTON_NO_ESYNC=1 gamemoderun %command% -skipintro")
            self.assertIsNone(tool)
            s = sd.summary(APPID, root, state)
            self.assertEqual((s["status"], s["step"], s["changed"], s["canTry"]), ("trying", "nofsync", True, True))
            # 2. WineD3D instead (the earlier fix's variables are taken out)
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "wined3d")
            self.assertEqual(sd.read_settings(root, local, APPID)[0],
                             "PROTON_USE_WINED3D=1 gamemoderun %command% -skipintro")
            # 3. Proton Experimental: the options as they were, the tool set for this game only
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "experimental")
            options, tool = sd.read_settings(root, local, APPID)
            self.assertEqual(options, "gamemoderun %command% -skipintro")
            self.assertEqual(tool["name"], "proton_experimental")
            # 4. no GE-Proton installed: skipped; 5. the older Proton
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "older")
            self.assertEqual(sd.read_settings(root, local, APPID)[1]["name"], "proton_9")
            self.assertFalse(sd.summary(APPID, root, state)["canTry"])
            self.assertIsNone(sd.try_next(root, local, APPID, path=state))
            self.assertEqual(sd.summary(APPID, root, state)["status"], "gave_up")
            # Undo: everything as before, the other games untouched, the game forgotten
            sd.undo(root, local, APPID, path=state)
            self.assertEqual(sd.read_settings(root, local, APPID), ("gamemoderun %command% -skipintro", None))
            self.assertEqual(sd.read_settings(root, local, "570")[0], "-novid")
            self.assertIsNone(sd.summary(APPID, root, state))
            config = (root / "config/config.vdf").read_text()
            self.assertIn("proton_experimental", config)                  # the default for every game stays

    def test_ge_proton_when_installed_and_the_users_own_tool_comes_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            own = {"name": "proton_8", "config": "", "priority": "250"}
            root, local = fake_steam(tmp, options="", tool=own)
            for name in ("GE-Proton9-20", "GE-Proton10-4", "GE-Proton10-12"):
                (root / "compatibilitytools.d" / name).mkdir(parents=True)
            game = {"step": 2}
            self.assertEqual(sd.STEPS[sd.next_step(game, root)][0], "ge")
            for _ in range(4):
                key = sd.try_next(root, local, APPID, path=state)
            self.assertEqual(key, "ge")
            self.assertEqual(sd.read_settings(root, local, APPID)[1]["name"], "GE-Proton10-12")
            sd.undo(root, local, APPID, path=state)
            self.assertEqual(sd.read_settings(root, local, APPID), ("", own))

    def test_a_linux_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, _local = fake_steam(tmp, proton=False)
            sd.record_run(APPID, 2, state)
            self.assertTrue(sd.summary(APPID, root, state)["native"])

    def test_old_style_options_only_arguments(self):
        self.assertEqual(sd.with_env("-dx11", ["PROTON_USE_WINED3D=1"]), "PROTON_USE_WINED3D=1 %command% -dx11")
        self.assertEqual(sd.with_env("", []), "")


if __name__ == "__main__":
    unittest.main()
