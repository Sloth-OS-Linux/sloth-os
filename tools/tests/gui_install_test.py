#!/usr/bin/env python3
"""The installer ISO, installed by "a person": a virtual machine starts the ISO, and this script clicks through the
real Sloth OS installer the way a user would, then starts the installed disk, signs in and waits for Sloth Welcome.

Nothing in the installer knows about this test (there is no unattended mode, on purpose): the script only looks at
the screen and uses the mouse and keyboard. It finds a button by reading the screen (tesseract OCR) and clicks the
middle of its text, so a moved button does not break it; a renamed one does (then update the texts below, they are
the English texts of iso/.../sloth_installer/translations/en.json and Sloth Welcome).

    sudo python3 tools/tests/gui_install_test.py <iso> <work folder>

Needs qemu-system-x86_64 with KVM, OVMF and tesseract. Every step saves a screenshot into <work folder>/shots, and the
last screen is kept as fail.png when a step fails (the CI uploads the folder).
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageOps

ISO, WORK = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
SHOTS = WORK / "shots"
DISK = WORK / "disk.qcow2"
FULL_NAME, PASSWORD = "Sloth Tester", "slothtest2026"
OVMF_CODE = next(p for p in ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_CODE.fd",
                             "/usr/share/edk2/ovmf/OVMF_CODE.fd") if os.path.exists(p))
OVMF_VARS = OVMF_CODE.replace("CODE", "VARS")


class Failed(Exception):
    pass


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class VM:
    """One QEMU run, driven through its QMP socket (screenshots, mouse, keyboard)."""

    def __init__(self, name, cdrom=None):
        self.name = name
        self.sock_path = WORK / f"qmp-{name}.sock"
        self.sock_path.unlink(missing_ok=True)
        args = ["qemu-system-x86_64", "-enable-kvm", "-machine", "q35", "-cpu", "host",
                "-smp", str(min(4, os.cpu_count() or 2)), "-m", "8192",
                "-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
                "-drive", f"if=pflash,format=raw,file={WORK / 'vars.fd'}",
                "-drive", f"file={DISK},format=qcow2,if=none,id=disk", "-device", "virtio-blk-pci,drive=disk,bootindex=2",
                "-device", "virtio-vga,xres=1280,yres=800", "-device", "qemu-xhci", "-device", "usb-tablet",
                "-display", "none", "-no-reboot",
                "-netdev", "user,id=net", "-device", "virtio-net-pci,netdev=net",
                "-qmp", f"unix:{self.sock_path},server=on,wait=off",
                "-serial", f"file:{WORK / f'serial-{name}.log'}"]
        if cdrom:
            args += ["-drive", f"file={cdrom},media=cdrom,readonly=on,if=none,id=cd",
                     "-device", "ide-cd,drive=cd,bootindex=1"]
        self.proc = subprocess.Popen(args)
        for _ in range(100):
            if self.sock_path.exists():
                break
            time.sleep(0.1)
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(self.sock_path))
        self.buf = b""
        self._read()                      # the greeting
        self.cmd("qmp_capabilities")
        self.size = (1280, 800)
        self.n = 0

    def _read(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise Failed("QEMU closed the QMP socket")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    def cmd(self, name, **args):
        self.sock.sendall(json.dumps({"execute": name, "arguments": args}).encode() + b"\n")
        while True:
            msg = self._read()
            if "event" in msg:
                continue
            if "error" in msg:
                raise Failed(f"QMP {name}: {msg['error']}")
            return msg.get("return")

    def alive(self):
        return self.proc.poll() is None

    def screen(self, keep=None):
        path = WORK / "screen.png"
        self.cmd("screendump", filename=str(path), format="png")
        img = Image.open(path)
        img.load()
        self.size = img.size
        if keep:
            self.n += 1
            shutil.copy(path, SHOTS / f"{self.name}-{self.n:02d}-{keep}.png")
        return img

    # --- reading the screen ---
    def readings(self, img):
        """The screen read twice: as it is (inverted on a dark theme), and with only the light text kept. Text on a
        button (its frame and background confuse the first way) only comes out the second way, dimmer text only the
        first way."""
        gray = ImageOps.grayscale(img).resize((img.width * 2, img.height * 2), Image.LANCZOS)
        dark = sum(gray.resize((64, 40)).getdata()) / (64 * 40) < 128
        plain = ImageOps.autocontrast(ImageOps.invert(gray) if dark else gray)
        yield self.words(plain)
        if dark:
            yield self.words(gray.point(lambda v: 0 if v > 160 else 255))

    def words(self, big):
        """The words of a (2x enlarged) screen with their boxes in screen pixels."""
        tmp = WORK / "ocr.png"
        big.save(tmp)
        out = subprocess.run(["tesseract", str(tmp), "stdout", "--psm", "11", "tsv"], capture_output=True,
                             text=True).stdout
        words = []
        for row in out.splitlines()[1:]:
            f = row.split("\t")
            if len(f) < 12 or not f[11].strip():
                continue
            left, top, w, h = (int(v) // 2 for v in f[6:10])
            words.append({"text": f[11].strip(), "key": (f[2], f[3], f[4]), "box": (left, top, w, h)})
        return words

    @staticmethod
    def _norm(word):
        return re.sub(r"^[^\w]+|[^\w]+$", "", word)

    def find(self, phrase, img=None):
        """The box of the phrase on the screen (the lowest one if it is there more than once), or None."""
        img = img or self.screen()
        want = [self._norm(w) for w in phrase.split()]
        for words in self.readings(img):
            box = self._match(words, want)
            if box:
                return box
        return None

    def _match(self, words, want):
        hits = []
        for i in range(len(words) - len(want) + 1):
            group = words[i:i + len(want)]
            # one line: each word starts to the right of the previous one, at about the same height
            first = group[0]["box"]
            mid = first[1] + first[3] / 2
            if any(abs(g["box"][1] + g["box"][3] / 2 - mid) > max(first[3], 8) * 0.7 for g in group[1:]) \
                    or any(b["box"][0] <= a["box"][0] for a, b in zip(group, group[1:])):
                continue
            if [self._norm(g["text"]) for g in group] == want:
                x0 = min(g["box"][0] for g in group)
                y0 = min(g["box"][1] for g in group)
                x1 = max(g["box"][0] + g["box"][2] for g in group)
                y1 = max(g["box"][1] + g["box"][3] for g in group)
                hits.append((x0, y0, x1, y1))
        return max(hits, key=lambda b: b[1]) if hits else None

    def wait(self, phrase, timeout, fail=()):
        """Waits until the phrase is on the screen; a phrase in fail ends the test at once."""
        log(f"[{self.name}] waiting for “{phrase}” (at most {timeout // 60} min)")
        end = time.time() + timeout
        while time.time() < end:
            if not self.alive():
                raise Failed(f"the virtual machine stopped while waiting for “{phrase}”")
            img = self.screen()
            box = self.find(phrase, img)
            if box:
                self.screen(keep=re.sub(r"\W+", "-", phrase.lower()).strip("-"))
                log(f"[{self.name}] found “{phrase}”")
                return box
            for bad in fail:
                if self.find(bad, img):
                    self.screen(keep="failed")
                    raise Failed(f"the screen says “{bad}”")
            time.sleep(5)
        raise Failed(f"“{phrase}” did not appear in {timeout // 60} minutes")

    # --- mouse and keyboard ---
    def click(self, phrase, timeout=120, ends=False):
        """Clicks the middle of the phrase. ends: the click switches the machine off (Restart with -no-reboot), so
        QEMU may close its socket while the button is still being released."""
        x0, y0, x1, y1 = self.wait(phrase, timeout)
        x, y = (x0 + x1) // 2, (y0 + y1) // 2
        w, h = self.size
        try:
            self.cmd("input-send-event", events=[
                {"type": "abs", "data": {"axis": "x", "value": x * 32767 // (w - 1)}},
                {"type": "abs", "data": {"axis": "y", "value": y * 32767 // (h - 1)}}])
            time.sleep(0.3)
            for down in (True, False):
                self.cmd("input-send-event", events=[{"type": "btn", "data": {"down": down, "button": "left"}}])
                time.sleep(0.1)
        except (OSError, Failed):
            if not ends:
                raise
        log(f"[{self.name}] clicked “{phrase}”")
        time.sleep(2)

    KEYS = {" ": "spc", "-": "minus", ".": "dot", "\n": "ret", "\t": "tab", "_": "minus"}

    def key(self, *names):
        self.cmd("send-key", keys=[{"type": "qcode", "data": n} for n in names])
        time.sleep(0.15)

    def type(self, text):
        for ch in text:
            if ch.isupper() or ch == "_":
                self.key("shift", self.KEYS.get(ch, ch.lower()))
            else:
                self.key(self.KEYS.get(ch, ch))

    def stop(self, timeout=180):
        """Waits for the machine to switch off by itself (-no-reboot: a restart ends QEMU); stops it after that."""
        try:
            self.proc.wait(timeout)
            return True
        except subprocess.TimeoutExpired:
            self.proc.kill()
            return False


def install():
    vm = VM("live", cdrom=ISO)
    try:
        # The live system starts and opens the installer by itself, full screen
        vm.wait("Welcome to Sloth OS", 15 * 60)
        vm.click("Install")
        vm.wait("Keyboard and time zone", 60)
        vm.click("Next")
        vm.wait("Create your account", 60)
        vm.click("e.g. Anna Smith")
        vm.type(FULL_NAME)
        vm.type("\t\t")                    # the username is filled in from the name; on to the password
        vm.type(PASSWORD + "\t" + PASSWORD + "\n")
        vm.wait("Where should we install it", 60)
        vm.click("Empty disk")
        vm.click("Next")
        vm.click("I understand that all data on the disk will be erased")
        vm.click("Start installing")
        vm.wait("Installation complete", 60 * 60, fail=("Installation failed",))
        vm.click("Restart", ends=True)
        if not vm.stop():
            log("the live system did not switch off by itself in 3 minutes")
    finally:
        if vm.alive():
            try:
                vm.screen(keep="last")
            except (OSError, Failed):
                pass
            vm.proc.kill()


def first_start():
    vm = VM("installed")
    try:
        # The sign-in screen shows the new account; its password field has the focus
        vm.wait(FULL_NAME, 15 * 60, fail=("emergency mode",))
        vm.type(PASSWORD + "\n")
        vm.wait("Let's go", 10 * 60)       # Sloth Welcome opens after the first sign-in
        vm.screen(keep="welcome")
    finally:
        if vm.alive():
            try:
                vm.screen(keep="last")
            except (OSError, Failed):
                pass
            vm.proc.kill()


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(OVMF_VARS, WORK / "vars.fd")
    DISK.unlink(missing_ok=True)
    subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", str(DISK), "64G"], check=True)
    started = time.time()
    try:
        install()
        log(f"installed in {(time.time() - started) / 60:.0f} min")
        first_start()
    except (Failed, OSError) as e:
        last = sorted(SHOTS.glob("*.png"), key=os.path.getmtime)
        if (WORK / "screen.png").exists():
            shutil.copy(WORK / "screen.png", SHOTS / "fail.png")
        log(f"FAILED: {e} (screenshots: {SHOTS}, last: {last[-1].name if last else '-'})")
        return 1
    log(f"OK: installed, started, signed in and Sloth Welcome opened ({(time.time() - started) / 60:.0f} min)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
