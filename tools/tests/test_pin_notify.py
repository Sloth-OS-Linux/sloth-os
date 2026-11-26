#!/usr/bin/env python3
"""The PIN notification after the update (sloth_center.pin_notify), without a desktop: the PIN's state and
notify-send are faked. It must speak up once per reason, never without a TPM or when the PIN already unlocks the
saved passwords, and again after a later password change."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="sloth-pin-notify-"))
os.environ.update(XDG_STATE_HOME=str(TMP / "state"), SLOTH_PIN_NOTIFY_SETTLE="0")
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/common"))
sys.path.insert(0, str(REPO / "files/system/usr/lib/sloth-os/sloth-center"))
try:  # sloth_center.i18n needs PySide6 only for its Qt part
    import PySide6.QtCore  # noqa: F401
except ImportError:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = object
    qtcore.Property = lambda *a, **k: (lambda f: f)
    qtcore.Signal = lambda *a, **k: None
    qtcore.Slot = lambda *a, **k: (lambda f: f)
    sys.modules["PySide6"] = types.ModuleType("PySide6")
    sys.modules["PySide6.QtCore"] = qtcore

from sloth_center import pin_notify as pn  # noqa: E402


class Desktop:
    """notify-send and the Sloth Center start, faked: what was shown and what the user clicked."""

    def __init__(self, click=""):
        self.click, self.shown, self.opened = click, [], []

    def run(self, cmd, **kw):
        self.shown.append(cmd)
        return types.SimpleNamespace(stdout=self.click + "\n", returncode=0)

    def popen(self, cmd, **kw):
        self.opened.append(cmd)


def state(set_=True, tpm=True, wallet=False, dropped=False):
    return {"set": set_, "tpm": tpm, "wallet": wallet, "dropped": dropped}


class PinNotifyTest(unittest.TestCase):
    def setUp(self):
        pn.SAID.unlink(missing_ok=True)
        self.status = state()
        self.tpm = True
        pn.pin_status = lambda user: self.status
        pn.has_tpm = lambda: self.tpm

    def sign_in(self, click=""):
        desk = Desktop(click)
        pn.subprocess.run, pn.subprocess.Popen = desk.run, desk.popen
        pn.main()
        return desk

    def test_old_pin_once_after_the_update(self):
        first = self.sign_in()
        self.assertEqual(len(first.shown), 1)
        self.assertIn("Change PIN", first.shown[0][-1])            # says where to do it
        self.assertIn("Account and security", first.shown[0][-1])
        self.assertEqual(self.sign_in().shown, [])                # the next sign-in: nothing again

    def test_set_it_up_now_opens_the_page(self):
        desk = self.sign_in(click="setup")
        self.assertEqual(desk.opened, [["sloth-center", "--page", "accounts"]])

    def test_nothing_when_it_already_unlocks(self):
        self.status = state(wallet=True)
        self.assertEqual(self.sign_in().shown, [])

    def test_nothing_without_a_pin_or_a_tpm(self):
        self.status = state(set_=False)
        self.assertEqual(self.sign_in().shown, [])
        self.status, self.tpm = state(), False
        self.assertEqual(self.sign_in().shown, [])
        self.status, self.tpm = state(tpm=False), True             # a PIN kept without a TPM (hash)
        self.assertEqual(self.sign_in().shown, [])

    def test_password_change_is_told_again(self):
        self.sign_in()                                            # the update: told once
        self.status = state(wallet=True)
        self.sign_in()                                            # set up with the password: done
        self.assertFalse(pn.SAID.exists())
        self.status = state(dropped=True)                         # later the password changed
        desk = self.sign_in()
        self.assertEqual(len(desk.shown), 1)
        self.assertIn("password changed", desk.shown[0][-1])
        self.assertEqual(self.sign_in().shown, [])                # and only once

    def test_old_then_changed_without_setting_it_up(self):
        self.sign_in()
        self.status = state(dropped=True)
        self.assertEqual(len(self.sign_in().shown), 1)            # a different reason: told


if __name__ == "__main__":
    unittest.main(verbosity=2)
