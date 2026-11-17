#!/usr/bin/env python3
"""Sloth Center in one window only (sloth_center/single_instance.py): the first start owns org.slothos.Center, a later
start hands its request over and quits. Needs PySide6, PyGObject and a session bus (run it under dbus-run-session);
without a bus the tests are skipped."""
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATHS = [str(REPO / "files/system/usr/lib/sloth-os/common"), str(REPO / "files/system/usr/lib/sloth-os/sloth-center")]
sys.path[:0] = PATHS

try:
    from gi.repository import Gio, GLib
    from PySide6.QtCore import QCoreApplication, QTimer
    from sloth_center import single_instance as si
    HAVE_BUS = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
except ImportError:
    HAVE_BUS = False

LATER = textwrap.dedent("""
    import sys
    sys.path[:0] = {paths!r}
    from sloth_center import single_instance as si
    print("forwarded" if si.claim_or_forward("drivers", "kcm_mouse", "--x", "steam:440") else "own window")
""").format(paths=PATHS)


def later_start(env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run([sys.executable, "-c", LATER], capture_output=True, text=True, timeout=30, env=env)


@unittest.skipUnless(HAVE_BUS, "needs a session bus (dbus-run-session)")
class SingleInstanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_1_first_start_owns_the_name(self):
        self.assertFalse(si.claim_or_forward("", "", "", ""))
        owner = Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
            GLib.Variant("(s)", (si.NAME,)), None, Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        self.assertTrue(owner)

    def test_2_later_start_is_handed_over(self):
        inst = si.SingleInstance()
        seen = []
        inst.openRequested.connect(
            lambda *a: seen.append(a + (os.environ.get("XDG_ACTIVATION_TOKEN"),)))
        os.environ.pop("XDG_ACTIVATION_TOKEN", None)
        result = {}

        def run_later():
            # in a thread of its own: this process must keep answering on the bus meanwhile
            import threading
            t = threading.Thread(target=lambda: result.update(r=later_start({"XDG_ACTIVATION_TOKEN": "tok-1"})))
            t.start()

            def wait():
                if t.is_alive():
                    QTimer.singleShot(50, wait)
                else:
                    self.app.quit()
            wait()
        QTimer.singleShot(0, run_later)
        QTimer.singleShot(20000, self.app.quit)
        self.app.exec()
        self.assertEqual(result["r"].stdout.strip(), "forwarded", result["r"].stderr)
        # the request arrived whole, with the token in the environment while the window comes forward …
        self.assertEqual(seen, [("drivers", "kcm_mouse", "--x", "steam:440", "tok-1")])
        # … and not left there afterwards
        self.assertNotIn("XDG_ACTIVATION_TOKEN", os.environ)

    def test_3_unanswered_name_opens_a_window_of_its_own(self):
        # a name owned by something that does not answer Open: the later start does not hang, it opens its own
        code = textwrap.dedent("""
            import sys, time
            from gi.repository import Gio, GLib
            c = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            c.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                        GLib.Variant("(su)", ("org.slothos.CenterX", 4)), None, Gio.DBusCallFlags.NONE, 3000, None)
            print("owned", flush=True)
            time.sleep(30)
        """)
        squatter = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(squatter.stdout.readline().strip(), "owned")
            later = LATER.replace("from sloth_center import single_instance as si",
                                  "from sloth_center import single_instance as si\nsi.NAME = 'org.slothos.CenterX'")
            r = subprocess.run([sys.executable, "-c", later], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.stdout.strip(), "own window", r.stderr)
        finally:
            squatter.kill()
            squatter.wait()
            squatter.stdout.close()


class NoBusTest(unittest.TestCase):
    @unittest.skipUnless("gi" in sys.modules or HAVE_BUS, "needs PyGObject")
    def test_without_a_bus_the_window_opens(self):
        env = {k: v for k, v in os.environ.items() if k != "DBUS_SESSION_BUS_ADDRESS"}
        env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/nonexistent/bus"
        r = subprocess.run([sys.executable, "-c", LATER], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(r.stdout.strip(), "own window", r.stderr)


if __name__ == "__main__":
    unittest.main()
