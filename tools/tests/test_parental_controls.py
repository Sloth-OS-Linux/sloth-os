#!/usr/bin/env python3
"""Parental controls without root, D-Bus or Qt: the screen time service's decisions (/usr/libexec/sloth-os/screen-time),
sloth-helper-family's checks, the child session's warnings and hidden apps (sloth_center.family_session) and the
username suggestion (sloth_center.family). The real services (AccountsService, malcontent-timerd) are tried by
tools/tests/parental_controls_test.sh in a container."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="sloth-family-"))
os.environ.update(SLOTH_FAMILY_STATE=str(TMP / "state"), XDG_RUNTIME_DIR=str(TMP / "run"),
                  XDG_DATA_HOME=str(TMP / "data"), USER="anna")
(TMP / "run").mkdir()
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
try:  # only the Qt part of the modules needs PySide6
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: (lambda f: f)
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import family, family_session  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, str(path)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


st = load("screen_time", REPO / "files/system/usr/libexec/sloth-os/screen-time")
web = load("family_web", REPO / "files/system/usr/libexec/sloth-os/family-web")
helper = load("sloth_helper", REPO / "files/system/usr/libexec/sloth-os/sloth-helper")


class Pw(types.SimpleNamespace):
    pass


ANNA = Pw(pw_name="anna", pw_uid=1001, pw_gid=1001, pw_shell="/bin/bash", pw_gecos="Anna")
PARENT = Pw(pw_name="parent", pw_uid=1000, pw_gid=1000, pw_shell="/bin/bash", pw_gecos="Parent")


class Stages(unittest.TestCase):
    def test_stages(self):
        self.assertEqual([st.stage_for(False, s) for s in (601, 600, 301, 300, 61, 60, 1, 0, -5)],
                         ["ok", "10", "10", "5", "5", "1", "1", "up", "up"])
        self.assertEqual(st.stage_for(True, 5000), "up")

    def test_usage_span(self):
        self.assertIsNone(st.usage_span(None, 100))           # the first round only starts counting
        self.assertEqual(st.usage_span(80, 100), (80, 100))
        self.assertIsNone(st.usage_span(100 - 3 * st.TICK - 1, 100))  # slept: not counted
        self.assertIsNone(st.usage_span(100, 100))            # never an empty span (timerd 0.14)
        self.assertIsNone(st.usage_span(120, 100))            # the clock went back


class ScreenTimeRounds(unittest.TestCase):
    def setUp(self):
        self.times = {}       # uid -> (reached, end, next) or None
        self.recorded = []
        self.written = {}
        self.removed = []
        self.terminated = []
        st.estimated = lambda pw: self.times.get(pw.pw_uid)
        st.record = lambda pw, a, b: self.recorded.append((pw.pw_name, a, b))
        st.write_state = lambda pw, state: self.written.__setitem__(pw.pw_name, dict(state))
        st.remove_state = lambda name: self.removed.append(name)
        st.is_admin = lambda pw: pw.pw_name == "parent"
        st.pwd = types.SimpleNamespace(getpwuid=lambda uid: {1001: ANNA, 1000: PARENT}[uid])
        test = self

        class Bus:
            sessions_value = {1001: [("3", True)], 1000: [("2", True)]}

            def sessions(self):
                return self.sessions_value

            def terminate(self, uid):
                test.terminated.append(uid)
        self.bus = Bus()
        self.service = st.ScreenTime(self.bus)

    def test_without_limit_nothing_happens(self):
        self.assertEqual(self.service.round(1000), {1001: None})
        self.assertEqual((self.recorded, self.written, self.terminated), ([], {}, []))

    def test_counting_warning_and_sign_out(self):
        self.times[1001] = (False, 2000, 9000)
        self.service.round(1000)
        self.assertEqual(self.recorded, [])               # the first round starts the count
        self.service.round(1020)
        self.assertEqual(self.recorded, [("anna", 1000, 1020)])
        self.assertEqual(self.written["anna"]["stage"], "ok")
        self.times[1001] = (False, 1500, 9000)
        self.service.round(1040)
        self.assertEqual(self.written["anna"], {"stage": "10", "end": 1500, "next": 9000})
        self.times[1001] = (True, 1060, 9000)
        self.service.round(1060)
        self.assertEqual(self.written["anna"]["stage"], "up")
        self.assertEqual(self.written["anna"]["logout"], 1060 + st.GRACE)
        self.assertEqual(self.terminated, [])
        self.service.round(1060 + st.GRACE)
        self.assertEqual(self.terminated, [1001])
        self.assertNotIn(1000, [u for u in self.terminated])  # the parent is never touched

    def test_more_time_takes_the_warning_back(self):
        self.times[1001] = (True, 1000, 9000)
        self.service.round(1000)
        self.times[1001] = (False, 2800, 9000)  # a parent allowed half an hour
        self.service.round(1020)
        self.assertEqual(self.written["anna"]["stage"], "ok")
        self.service.round(1020 + st.GRACE)
        self.assertEqual(self.terminated, [])

    def test_locked_screen_is_not_counted(self):
        self.times[1001] = (False, 5000, 9000)
        self.bus.sessions_value = {1001: [("3", False)]}
        self.service.round(1000)
        self.service.round(1020)
        self.assertEqual(self.recorded, [])

    def test_signing_out_removes_the_state(self):
        self.times[1001] = (False, 5000, 9000)
        self.service.round(1000)
        self.bus.sessions_value = {}
        self.service.round(1020)
        self.assertEqual(self.removed, ["anna"])

    def test_a_broken_timerd_signs_nobody_out(self):
        def broken(pw):
            raise RuntimeError("timerd is gone")
        st.estimated = broken
        self.service.round(1000)
        self.service.round(5000)
        self.assertEqual(self.terminated, [])


class FakeBuilder:
    def __init__(self, log):
        self.log = log

    def __getattr__(self, name):
        return lambda *a: self.log.append((name, a))

    def end(self):
        return ("limits", tuple(self.log))


class HelperChecks(unittest.TestCase):
    def setUp(self):
        self.calls = []
        calls = self.calls
        malcontent = types.SimpleNamespace(
            SessionLimitsBuilder=types.SimpleNamespace(new=lambda: FakeBuilder(calls)),
            AppFilterBuilder=types.SimpleNamespace(new=lambda: FakeBuilder(calls)),
            ManagerSetValueFlags=types.SimpleNamespace(NONE=0))
        manager = types.SimpleNamespace(
            set_session_limits=lambda uid, limits, flags, c: calls.append(("set_session_limits", uid)),
            set_app_filter=lambda uid, f, flags, c: calls.append(("set_app_filter", uid)))
        helper._malcontent = lambda: (malcontent, manager)
        helper.FAMILY_STATE = str(TMP / "helper-state")
        users = {"anna": ANNA, "parent": PARENT, "root": Pw(pw_name="root", pw_uid=0, pw_gid=0, pw_shell="/bin/bash"),
                 "svc": Pw(pw_name="svc", pw_uid=1003, pw_gid=1003, pw_shell="/sbin/nologin")}

        def getpwnam(name):
            if name not in users:
                raise KeyError(name)
            return users[name]
        helper.pwd = types.SimpleNamespace(getpwnam=getpwnam, getpwuid=lambda uid: PARENT)
        helper.grp = types.SimpleNamespace(getgrnam=lambda n: types.SimpleNamespace(gr_mem=["parent"], gr_gid=10))
        os.environ["PKEXEC_UID"] = "1000"

    def test_only_ordinary_accounts_other_than_the_caller(self):
        self.assertIsNotNone(helper._child("anna"))
        for name in ("parent", "root", "svc", "nobody-here"):
            self.assertIsNone(helper._child(name), name)
        os.environ["PKEXEC_UID"] = "1001"
        helper.pwd.getpwuid = lambda uid: ANNA
        self.assertIsNone(helper._child("anna"))  # not your own limits

    def test_limits(self):
        ok = helper.child_limits("anna", {"daily": 3600, "start": 16 * 3600, "end": 20 * 3600})
        self.assertEqual(ok, {"ok": True})
        self.assertIn(("set_daily_schedule", (True, 16 * 3600, 20 * 3600)), self.calls)
        self.assertIn(("set_daily_limit", (True, 3600)), self.calls)
        self.calls.clear()
        helper.child_limits("anna", {"daily": 0, "start": None, "end": None})
        self.assertIn(("set_none", ()), self.calls)
        for bad in ({"daily": -1}, {"daily": True}, {"daily": "60"}, {"daily": 86401},
                    {"daily": 0, "start": 7200, "end": 3600}, {"daily": 0, "start": 0, "end": None},
                    {"daily": 0, "start": 0, "end": 90000}):
            self.assertEqual(helper.child_limits("anna", bad)["error"], "bad input", bad)
        self.assertEqual(helper.child_limits("parent", {"daily": 60})["error"], "not a child account")

    def test_apps(self):
        refs = ["app/org.mozilla.firefox/x86_64/stable", "app/com.valvesoftware.Steam/x86_64/stable"]
        self.assertEqual(helper.child_apps("anna", {"blocked": refs}), {"ok": True})
        self.assertIn(("blocklist_flatpak_ref", (refs[1],)), self.calls)
        self.assertIn(("set_allow_user_installation", (False,)), self.calls)
        self.assertTrue((TMP / "helper-state" / "anna.apps").exists())
        for bad in (["../x"], ["app/org.x/x86_64/stable;rm"], ["runtime/org.x.Y/x86_64/1"], "app/a.b.c/x/y", [1]):
            self.assertEqual(helper.child_apps("anna", {"blocked": bad})["error"], "bad input", bad)

    def test_programs_switch(self):
        self.assertEqual(helper.child_apps("anna", {"blocked": [], "programs": False}), {"ok": True})
        self.assertIn(("blocklist_content_type", ("application/x-ms-dos-executable",)), self.calls)
        self.assertIn(("blocklist_content_type", ("application/vnd.appimage",)), self.calls)
        self.calls.clear()
        helper.child_apps("anna", {"blocked": []})  # left out: allowed, as before
        self.assertFalse([c for c in self.calls if c[0] == "blocklist_content_type"])
        self.assertEqual(helper.child_apps("anna", {"blocked": [], "programs": "no"})["error"], "bad input")

    def test_web_filter_list(self):
        helper.FAMILY_WEB = str(TMP / "family-web.json")
        ran = []
        helper.run = lambda cmd, **k: ran.append(cmd) or types.SimpleNamespace(returncode=0, stderr="")
        self.assertEqual(helper.child_web("anna", True), {"ok": True})
        self.assertEqual(json.loads(Path(helper.FAMILY_WEB).read_text()), {"users": ["anna"]})
        self.assertEqual(ran, [["/usr/libexec/sloth-os/family-web"]])  # in effect at once
        helper.child_web("anna", True)
        self.assertEqual(helper.web_users(), ["anna"])  # not twice
        helper.child_web("anna", False)
        self.assertEqual(helper.web_users(), [])
        self.assertEqual(helper.child_web("parent", True)["error"], "not a child account")

    def test_add_checks(self):
        helper.run = lambda *a, **k: self.fail("must not run anything")
        for bad in ({"username": "Anna", "fullname": "A", "password": "x"},
                    {"username": "anna2", "fullname": "A:B", "password": "x"},
                    {"username": "anna2", "fullname": "A", "password": ""},
                    {"username": "anna2", "fullname": "A", "password": "a\nb"},
                    {"username": "anna2", "fullname": 5, "password": "x"}):
            self.assertEqual(helper.child_add(bad)["error"], "bad input", bad)
        self.assertEqual(helper.child_add({"username": "anna", "fullname": "A", "password": "x"})["error"], "exists")


class WebFilter(unittest.TestCase):
    def setUp(self):
        users = {"anna": ANNA, "parent": PARENT, "svc": Pw(pw_name="svc", pw_uid=980, pw_gid=980, pw_shell="/bin/bash")}

        def getpwnam(name):
            if name not in users:
                raise KeyError(name)
            return users[name]
        web.pwd = types.SimpleNamespace(getpwnam=getpwnam)
        web.grp = types.SimpleNamespace(getgrnam=lambda n: types.SimpleNamespace(gr_mem=["parent"], gr_gid=10))
        self.config = TMP / "web.json"

    def test_only_children_are_filtered(self):
        self.config.write_text(json.dumps({"users": ["anna", "parent", "svc", "gone", 5]}))
        self.assertEqual(web.children(str(self.config)), [1001])  # never a parent or a system account
        for bad in ("", "[]", '{"users": "anna"}', "not json"):
            self.config.write_text(bad)
            self.assertEqual(web.children(str(self.config)), [], bad)

    def test_rules(self):
        rules = web.ruleset([1001, 1002])
        self.assertIn("elements = { 1001, 1002 }", rules)
        self.assertIn("dnat ip to 127.0.0.2:53", rules)
        self.assertIn("tcp dport 853 reject", rules)
        self.assertTrue(rules.startswith("table inet sloth_family\ndelete table inet sloth_family\n"))
        # every rule is for the children's sockets only: a parent's traffic is never touched
        for line in rules.splitlines():
            if "dport" in line:
                self.assertIn("meta skuid @children", line)


class ChildSession(unittest.TestCase):
    def setUp(self):
        family_session.SEEN.unlink(missing_ok=True)
        family_session.STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.started = []
        test = self

        class Proc:
            pid = 4242

        def popen(cmd, **kw):
            test.started.append(cmd)
            return Proc()
        family_session.subprocess = types.SimpleNamespace(Popen=popen, run=lambda *a, **k: None, PIPE=-1)

    def state(self, **state):
        (family_session.STATE_DIR / "anna.json").write_text(json.dumps(state))

    def test_each_stage_once(self):
        now = int(time.time())
        self.state(stage="10", end=now + 600, next=now + 86400)
        family_session.screen_time()
        family_session.screen_time()  # the same stage again: nothing new
        self.assertEqual(len(self.started), 1)
        title, text, ask = json.loads(self.started[0][-1])
        self.assertTrue(ask and "10" in text)
        self.state(stage="up", end=now, next=now + 86400, logout=now + 60)
        family_session.screen_time()
        title, text, ask = json.loads(self.started[1][-1])
        self.assertEqual(title, "Time's up")
        self.state(stage="ok", end=now + 1800, next=now + 86400)
        family_session.screen_time()
        title, text, ask = json.loads(self.started[2][-1])
        self.assertFalse(ask)
        self.assertIn("more time", text)

    def test_when_again(self):
        t = time.localtime()
        tomorrow = time.mktime((t.tm_year, t.tm_mon, t.tm_mday + 1, 0, 0, 0, 0, 0, -1))
        self.assertEqual(family_session.when_again(tomorrow), "You can use the computer again tomorrow.")
        self.assertIn("tomorrow at", family_session.when_again(tomorrow + 16 * 3600))
        later = time.time() + 60
        if time.localtime(later).tm_mday == t.tm_mday:
            self.assertIn("again at", family_session.when_again(later))

    def test_hidden_apps(self):
        exports = TMP / "exports"
        exports.mkdir(exist_ok=True)
        for app in ("org.mozilla.firefox", "org.kde.kcalc"):
            (exports / f"{app}.desktop").write_text(f"[Desktop Entry]\nName={app}\nX-Flatpak={app}\n")
        family_session.EXPORTS = [exports]
        blocked = {"org.mozilla.firefox"}
        family_session._app_filter = lambda: types.SimpleNamespace(is_flatpak_app_allowed=lambda a: a not in blocked)
        own = family_session.APPS_DIR / "org.kde.kcalc.desktop"
        family_session.APPS_DIR.mkdir(parents=True, exist_ok=True)
        own.write_text("[Desktop Entry]\nName=My own calculator entry\n")
        family_session.hide_blocked_apps()
        hidden = family_session.APPS_DIR / "org.mozilla.firefox.desktop"
        self.assertIn("Hidden=true", hidden.read_text())
        blocked.add("org.kde.kcalc")
        family_session.hide_blocked_apps()
        self.assertNotIn("Hidden", own.read_text())  # the user's own entry is left alone
        blocked.clear()
        family_session.hide_blocked_apps()
        self.assertFalse(hidden.exists())
        self.assertTrue(own.exists())


class Usernames(unittest.TestCase):
    def test_suggest(self):
        self.assertEqual(family.suggest_username("Kis Péter"), "kispeter")
        self.assertEqual(family.suggest_username("Ágnes-Zoé 2"), "agneszoe2")
        self.assertEqual(family.suggest_username("123"), "")
        self.assertEqual(family.suggest_username("李"), "")


if __name__ == "__main__":
    unittest.main()
