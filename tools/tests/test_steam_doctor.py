#!/usr/bin/env python3
"""What's wrong with the game? (sloth_common/steam_doctor.py): a Steam game that closes right after starting, the fixes
one after the other in Steam's own files (launch options, compatibility tool), and Undo; the shared knowledge's
setting first, and the reports. A fake Steam folder, a fake knowledge.json."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOME = Path(tempfile.mkdtemp(prefix="sloth-doctor-"))
os.environ.update(XDG_CACHE_HOME=str(HOME / "cache"), XDG_CONFIG_HOME=str(HOME / "config"),
                  XDG_STATE_HOME=str(HOME / "state"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))

from sloth_common import knowledge, sharing  # noqa: E402
from sloth_common import steam_doctor as sd  # noqa: E402
from sloth_common.apps import steam  # noqa: E402

knowledge.gpu_vendor = lambda: "amd"

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
            game = {"step": 3}
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


def set_knowledge(games=None, programs=None):
    knowledge.CACHE.parent.mkdir(parents=True, exist_ok=True)
    knowledge.CACHE.write_text(json.dumps({"version": 1, "games": games or {}, "programs": programs or {}}))


def reports(queue=None):
    queue = queue or sharing.GAMES_QUEUE
    if not queue.exists():
        return []
    return [json.loads(line) for line in queue.read_text().splitlines()]


class Shared(unittest.TestCase):
    def setUp(self):
        sharing.set_enabled(False)
        sharing.set_games_enabled(False)
        knowledge.CACHE.unlink(missing_ok=True)

    def test_the_knowledge_first_then_the_ladder_without_repeating_it(self):
        set_knowledge({f"umu-{APPID}": {"any": {"line": "UMU-Proton", "profile": "wined3d", "reports": 9,
                                                 "fixes": [["env", "PROTON_NO_D3D11"], ["verb", "vcrun2022"]]}}})
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp, options="-skipintro")
            sd.record_run(APPID, 3, state)
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "shared")
            # the profile and the switch go into the launch options; a component cannot, it is left out
            self.assertEqual(sd.read_settings(root, local, APPID),
                             ("PROTON_USE_WINED3D=1 PROTON_NO_D3D11=1 %command% -skipintro", None))
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "nofsync")
            self.assertEqual(sd.read_settings(root, local, APPID)[0],
                             "PROTON_NO_FSYNC=1 PROTON_NO_ESYNC=1 %command% -skipintro")
            sd.undo(root, local, APPID, path=state)
            self.assertEqual(sd.read_settings(root, local, APPID), ("-skipintro", None))

    def test_a_fix_the_knowledge_already_tried_is_skipped(self):
        set_knowledge({f"umu-{APPID}": {"amd": {"line": "UMU-Proton", "profile": "nofsync", "fixes": []}}})
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp)
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "shared")
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "wined3d")

    def test_sloth_machines_first_and_ge_only_when_installed(self):
        set_knowledge({f"umu-{APPID}": {"any": {"line": "UMU-Proton", "profile": "wined3d", "fixes": []}}},
                      {knowledge.steam_key(APPID): {"amd": {"line": "GE-Proton", "profile": "default",
                                                            "fixes": [], "machines": 4}}})
        with tempfile.TemporaryDirectory() as tmp:
            root, local = fake_steam(tmp)
            self.assertIsNone(sd.shared_setting(APPID, root))     # GE-Proton is not there: nothing to give Steam
            (root / "compatibilitytools.d/GE-Proton10-12").mkdir(parents=True)
            words, tool, config = sd.shared_setting(APPID, root)
            self.assertEqual((words, tool, config["line"]), ([], "GE-Proton10-12", "GE-Proton"))
            state = Path(tmp, "doctor.json")
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "shared")
            self.assertEqual(sd.read_settings(root, local, APPID)[1]["name"], "GE-Proton10-12")

    def test_nothing_known_or_only_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _local = fake_steam(tmp)
            self.assertIsNone(sd.shared_setting(APPID, root))
            set_knowledge({f"umu-{APPID}": {"any": {"line": "UMU-Proton", "profile": "default", "fixes": []}}})
            self.assertIsNone(sd.shared_setting(APPID, root))
            self.assertEqual(sd.STEPS[sd.next_step({}, root, APPID)][0], "nofsync")

    def test_reports_only_with_the_games_switch_on(self):
        set_knowledge({f"umu-{APPID}": {"any": {"line": "UMU-Proton", "profile": "wined3d", "fixes": []}}})
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp)
            sd.record_run(APPID, 3, state)
            sd.try_next(root, local, APPID, path=state)
            sharing.set_enabled(True)                              # the Windows programs' yes is not enough
            sd.record_run(APPID, 300, state)
            self.assertEqual((reports(), reports(sharing.QUEUE)), ([], []))
            sharing.set_games_enabled(True)
            sd.record_run(APPID, 3, state)                         # the setting stopped working
            sd.try_next(root, local, APPID, path=state)            # nofsync
            sd.record_run(APPID, 3, state)                         # it did not help either
            sd.try_next(root, local, APPID, path=state)            # experimental: no word for it
            sd.record_run(APPID, 3, state)
            sd.try_next(root, local, APPID, path=state)            # older
            sd.record_run(APPID, 400, state)
            got = [(r["program"], r["line"], r["profile"], r["fixes"], r["outcome"], r["gpu"]) for r in reports()]
            key = knowledge.steam_key(APPID)
            self.assertEqual(got, [(key, "UMU-Proton", "wined3d", [], "failed", "amd"),
                                   (key, "UMU-Proton", "nofsync", [], "failed", "amd")])
            self.assertEqual(reports(sharing.QUEUE), [])           # not in the Windows programs' queue
            sharing.set_games_enabled(False)                       # off: the unsent ones go too
            self.assertFalse(sharing.GAMES_QUEUE.exists())
            sharing.set_enabled(False)

    def test_a_disputed_setting_is_skipped_and_said(self):
        wined3d = {"line": "UMU-Proton", "profile": "wined3d", "fixes": [], "reports": 9, "last": "2026-08"}
        nofsync = {"line": "UMU-Proton", "profile": "nofsync", "fixes": [], "machines": 4, "last": "2026-11"}
        key = knowledge.steam_key(APPID)
        # Sloth OS machines' own setting first, with its players and month
        set_knowledge({f"umu-{APPID}": {"any": wined3d}}, {key: {"amd": nofsync}})
        self.assertEqual(sd.shared_info(APPID), {"players": 4, "last": "2026-11", "source": "sloth",
                                                  "disputed": False})
        # that one failed on several machines lately: ProtonDB's comes next
        knowledge.CACHE.write_text(json.dumps({"games": {f"umu-{APPID}": {"any": wined3d}},
                                               "programs": {key: {"amd": nofsync}},
                                               "disputed": {key: {"amd": [{"line": "UMU-Proton",
                                                                           "profile": "nofsync", "fixes": []}]}}}))
        self.assertEqual(sd.shared_info(APPID)["source"], "protondb")
        with tempfile.TemporaryDirectory() as tmp:
            root, _local = fake_steam(tmp)
            self.assertEqual(sd.shared_setting(APPID, root)[0], ["PROTON_USE_WINED3D=1"])
        # every setting disputed: nothing is offered, and it says why
        knowledge.CACHE.write_text(json.dumps({"games": {f"umu-{APPID}": {"any": wined3d}}, "programs": {},
                                               "disputed": {key: {"amd": [wined3d]}}}))
        self.assertEqual(sd.shared_info(APPID), {"players": 9, "last": "2026-08", "source": "protondb",
                                                  "disputed": True})
        with tempfile.TemporaryDirectory() as tmp:
            root, _local = fake_steam(tmp)
            self.assertIsNone(sd.shared_setting(APPID, root))

    def test_it_starts_but_does_not_work_right(self):
        set_knowledge({f"umu-{APPID}": {"any": {"line": "UMU-Proton", "profile": "wined3d", "fixes": []}}})
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            root, local = fake_steam(tmp)
            self.assertFalse(sd.not_right(APPID, state))            # nothing tried yet: nothing to say
            sd.record_run(APPID, 3, state)
            sd.try_next(root, local, APPID, path=state)              # the shared setting
            sd.record_run(APPID, 600, state)                         # "works": it ran for 10 minutes
            sharing.set_games_enabled(True)
            self.assertTrue(sd.not_right(APPID, state))              # ... but not right
            s = sd.summary(APPID, root, state)
            self.assertEqual((s["status"], s["canTry"], s["sharing"]), ("failing", True, True))
            self.assertEqual([(r["profile"], r["outcome"]) for r in reports()], [("wined3d", "failed")])
            self.assertEqual(sd.try_next(root, local, APPID, path=state), "nofsync")
            sharing.set_games_enabled(False)

    def test_a_state_from_before_the_shared_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp, "doctor.json")
            state.write_text(json.dumps({APPID: {"failures": [], "step": 0, "original": {"options": "", "tool": None},
                                                 "status": "trying"}}))
            self.assertEqual(sd.summary(APPID, path=state)["step"], "nofsync")


if __name__ == "__main__":
    unittest.main()
