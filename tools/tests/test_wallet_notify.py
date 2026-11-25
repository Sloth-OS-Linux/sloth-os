#!/usr/bin/env python3
"""The saved passwords notification on an automatic sign-in (sloth_center.wallet_notify), without D-Bus or a
desktop: busctl's answers and notify-send are faked."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="sloth-wallet-"))
os.environ.update(XDG_STATE_HOME=str(TMP / "state"), SLOTH_WALLET_SETTLE="0")
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

from sloth_center import wallet_notify as wn  # noqa: E402


class Store:
    """busctl's answers for a password store: enabled, its default wallet, the wallets, open or not."""

    def __init__(self, enabled=True, exists=True, is_open=False):
        self.enabled, self.exists, self.is_open = enabled, exists, is_open
        self.opened = []

    def __call__(self, method, signature="", *args, timeout=10):
        if method == "isEnabled":
            return "b true" if self.enabled else "b false"
        if method == "localWallet":
            return 's "kdewallet"'
        if method == "wallets":
            return 'as 1 "kdewallet"' if self.exists else "as 0"
        if method == "isOpen":
            return "b true" if self.is_open else "b false"
        if method == "open":
            self.opened.append(args)
            return "i 1"
        return None


class WalletNotify(unittest.TestCase):
    def setUp(self):
        self.policy = TMP / "admin-policy.json"
        self.policy.write_text(json.dumps({"users": {"anna": {"autologin": True}, "bob": {"autologin": False}}}))
        wn.POLICY = str(self.policy)
        wn.QUIET = TMP / "state" / "sloth-os" / "wallet-notify-off"
        if wn.QUIET.exists():
            wn.QUIET.unlink()
        wn.getpass = types.SimpleNamespace(getuser=lambda: "anna")
        self.sent = []
        self.answer = ""

        def run(cmd, **kw):
            self.sent.append(cmd)
            return types.SimpleNamespace(stdout=self.answer, returncode=0)
        wn.subprocess = types.SimpleNamespace(run=run, SubprocessError=Exception)

    def test_locked_on_autologin(self):
        wn.wallet_call = store = Store()
        self.answer = "unlock\n"
        wn.main()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("--action=unlock=Unlock now", self.sent[0])
        self.assertEqual(store.opened, [("kdewallet", 0, "Sloth OS")])

    def test_dont_remind(self):
        wn.wallet_call = Store()
        self.answer = "quiet\n"
        wn.main()
        self.assertTrue(wn.QUIET.exists())
        self.sent.clear()
        wn.main()
        self.assertEqual(self.sent, [])     # never again for this account

    def test_silent_cases(self):
        for store in (Store(is_open=True),      # the boot password opened it (encrypted disk)
                      Store(exists=False),      # nothing saved yet
                      Store(enabled=False)):    # the store is off (the guest)
            wn.wallet_call = store
            wn.main()
        self.assertEqual(self.sent, [])
        wn.wallet_call = Store()
        wn.getpass = types.SimpleNamespace(getuser=lambda: "bob")   # signed in with a password
        wn.main()
        self.assertEqual(self.sent, [])

    def test_no_store_service(self):
        wn.wallet_call = lambda *a, **k: None   # busctl failed: say nothing
        self.assertEqual(wn.locked_wallet(), "")


if __name__ == "__main__":
    unittest.main()
