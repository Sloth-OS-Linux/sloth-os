#!/usr/bin/env python3
"""The diagnostic information of a feedback (sloth_center/diagnostics.py): every personal detail out, everything that
helps find the problem kept (times, versions, Sloth OS's own names), on lines like the journal's."""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))

from sloth_center import diagnostics as d  # noqa: E402

FACTS = {"users": ["anna", "test"], "names": ["Kovács Anna"], "host": "annas-laptop",
         "networks": ["Kovacs otthon 5G", "Telekom-ABCD12"], "ids": ["4b8e9ae2edb44a34b2a80ff9c7ac82f5"]}

LOG = """nov 18 10:10:44 annas-laptop systemd[2555]: Started app-org.slothos.welcome@autostart.service - Sloth Welcome.
nov 18 10:10:44 annas-laptop sloth-tv-session[4598]: gamescope ended (exit code 141)
nov 18 10:10:45 annas-laptop kwin_wayland[1200]: file:///home/anna/.config/kwinrc and /var/home/test/x.log
nov 18 10:10:46 annas-laptop NetworkManager[900]: <info> device (wlp2s0): Activation: starting connection 'Kovacs otthon 5G' (b1c2)
nov 18 10:10:46 annas-laptop NetworkManager[900]: <info> dhcp4 (wlp2s0): address 192.168.1.37, gateway 192.168.1.1
nov 18 10:10:46 annas-laptop NetworkManager[900]: <info> dhcp6: address 2a02:ab88:1234:5600:1c2d:3e4f:5a6b:7c8d/128 fe80::1c2d:3e4f:5a6b:7c8d
nov 18 10:10:47 annas-laptop kernel: wlp2s0: authenticate with 3c:a6:2f:12:34:56 (try 1/3)
nov 18 10:10:47 annas-laptop kernel: listening on 127.0.0.1:631 and 0.0.0.0, ::1, version 6.17.12-300.fc44
nov 18 10:10:48 annas-laptop sloth-center[3000]: feedback from anna.kovacs@example.com for Kovács Anna
nov 18 10:10:48 annas-laptop systemd[1]: machine id 4b8e9ae2edb44a34b2a80ff9c7ac82f5 on "Telekom-ABCD12"
    Serial:                     S5GXNX0T123456K
    WWN:                        eui.0025385b71b0a1c2
nov 18 10:10:49 annas-laptop plasmashell[1500]: PLASMALOGIN::Session Bad::Add Steam AppID 1245620, 44.20261117
kernel 6.6.87.2-microsoft-standard-WSL2 and v1.2.3.4 and peer 10.0.0.5:443
"""


class Redact(unittest.TestCase):
    def setUp(self):
        self.out = d.redact(LOG, FACTS)

    def test_personal_details_gone(self):
        for secret in ("anna", "Anna", "/home/anna", "/var/home/test", "annas-laptop", "Kovacs otthon 5G",
                       "Telekom-ABCD12", "192.168.1.37", "192.168.1.1", "2a02:ab88", "fe80::1c2d",
                       "3c:a6:2f:12:34:56", "anna.kovacs@example.com", "Kovács", "S5GXNX0T123456K",
                       "eui.0025385b71b0a1c2", "4b8e9ae2edb44a34b2a80ff9c7ac82f5", "10.0.0.5"):
            self.assertNotIn(secret, self.out, secret)

    def test_placeholders_say_what_was_there(self):
        for mark in ("<user>", "<name>", "<computer>", "<network>", "<ip>", "<mac>", "<email>", "<serial>"):
            self.assertIn(mark, self.out, mark)
        self.assertIn("file:///home/<user>/.config/kwinrc", self.out)
        self.assertIn("/var/home/<user>/x.log", self.out)

    def test_useful_details_kept(self):
        for kept in ("nov 18 10:10:44", "10:10:49", "sloth-tv-session[4598]", "exit code 141", "127.0.0.1:631",
                     "0.0.0.0", "::1", "6.17.12-300.fc44", "44.20261117", "AppID 1245620", "PLASMALOGIN::Session",
                     "Bad::Add", "org.slothos.welcome", "wlp2s0", "6.6.87.2-microsoft-standard-WSL2",
                     "v1.2.3.4"):
            self.assertIn(kept, self.out, kept)

    def test_common_host_name_kept(self):
        # every Sloth OS is "sloth": it says nothing about the person, and it is in Sloth OS's own names
        out = d.redact("nov 18 10:10:44 sloth sloth-center[1]: sloth-os ok\n",
                       dict(FACTS, host="sloth", users=["zsolt"]))
        self.assertEqual(out, "nov 18 10:10:44 sloth sloth-center[1]: sloth-os ok\n")

    def test_user_name_inside_longer_names_kept(self):
        # the user "sloth": sloth-tv-session and org.slothos stay, the home folder goes
        out = d.redact("sloth-tv-session /home/sloth/x org.slothos.center\n", dict(FACTS, users=["sloth"]))
        self.assertEqual(out, "sloth-tv-session /home/<user>/x org.slothos.center\n")


class Sending(unittest.TestCase):
    def test_sends_exactly_the_text_shown(self):
        import json
        from unittest import mock
        from sloth_center import feedback
        shown = d.redact(LOG, FACTS)
        sent = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"number": 7}'

        def urlopen(req, timeout):
            sent.update(json.loads(req.data))
            return Resp()
        with mock.patch.object(feedback.urllib.request, "urlopen", urlopen),                 mock.patch.object(feedback.diagnostics, "bundle", side_effect=AssertionError("collected again")):
            ok, number = feedback.send("bug", "It froze after Sleep in TV mode.", True, shown)
        self.assertEqual((ok, number), (True, 7))
        self.assertEqual(sent["log"], shown)
        self.assertNotIn("anna", sent["log"])

    def test_without_log_nothing_collected(self):
        from unittest import mock
        from sloth_center import feedback
        with mock.patch.object(feedback.urllib.request, "urlopen", side_effect=OSError("offline")),                 mock.patch.object(feedback.diagnostics, "bundle", side_effect=AssertionError("collected")):
            self.assertEqual(feedback.send("idea", "A dark mode for the installer.", False), (False, "network"))


class Collect(unittest.TestCase):
    def test_sections(self):
        names = [title for title, _cmd in d.EXTRA]
        self.assertIn("The end of the previous start", names)
        self.assertIn("Errors of this start", names)


if __name__ == "__main__":
    unittest.main()
