#!/usr/bin/env python3
"""Shows the fastfetch logo in the terminal with its real colors, with the system details beside it
(also on Windows, in Windows Terminal or the VS Code terminal).

Usage: python tools/branding/show_fastfetch_logo.py
If fastfetch is installed, it runs with Sloth OS's config and logo (this machine's real details); otherwise the
logo is shown with an example of what Sloth OS prints. The colors come from files/system/etc/fastfetch/config.jsonc.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOGO = REPO / "files/system/usr/share/sloth-os/logo/sloth-ascii.txt"
CONFIG = REPO / "files/system/etc/fastfetch/config.jsonc"
EXAMPLE = [
    ("", "anna@sloth-os"),
    ("", "-------------"),
    ("OS", "Sloth OS 1.1 (Fedora Atomic 44) x86_64"),
    ("Host", "HP EliteDesk 800 G4 SFF"),
    ("Kernel", "Linux 6.17.4-300.fc44.x86_64"),
    ("Uptime", "2 hours, 14 mins"),
    ("Packages", "1964 (rpm), 23 (flatpak)"),
    ("Shell", "bash 5.3.9"),
    ("Display", "1920x1080 @ 60 Hz in 27\" [External]"),
    ("DE", "KDE Plasma 6.5.2"),
    ("WM", "KWin (Wayland)"),
    ("Terminal", "konsole 25.8.2"),
    ("", ""),
    ("CPU", "Intel(R) Core(TM) i7-8700 (12) @ 4.60 GHz"),
    ("GPU", "AMD Radeon RX 6600 [Discrete]"),
    ("Memory", "3.58 GiB / 31.21 GiB (11%)"),
    ("Swap", "0 B / 8.00 GiB (0%)"),
    ("Disk (/)", "48.20 GiB / 476.34 GiB (10%) - btrfs"),
]


def config():
    return json.loads(re.sub(r"^\s*//.*$", "", CONFIG.read_text(encoding="utf-8"), flags=re.M))


def with_fastfetch(cfg):
    """fastfetch with Sloth OS's config, the logo from the repository."""
    cfg["logo"]["source"] = str(LOGO)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonc", delete=False, encoding="utf-8") as f:
        json.dump(cfg, f)
    try:
        return subprocess.run(["fastfetch", "-c", f.name, "--pipe", "false"]).returncode == 0
    finally:
        os.unlink(f.name)


def example(cfg):
    colors = {n: f"\x1b[{code}m" for n, code in cfg["logo"]["color"].items()}
    keys, title = (f"\x1b[{cfg['display']['color'][k]}m" for k in ("keys", "title"))
    reset = "\x1b[0m"
    art = LOGO.read_text(encoding="utf-8").splitlines()
    width = max(len(re.sub(r"\$\d", "", line)) for line in art) + cfg["logo"]["padding"]["right"]
    info = [("", "")] * cfg["logo"]["padding"]["top"] + EXAMPLE
    print("\n(example: on Sloth OS fastfetch prints this machine's real details)\n")
    for i in range(max(len(art), len(info))):
        line = art[i] if i < len(art) else ""
        plain = re.sub(r"\$\d", "", line)
        for n, code in colors.items():
            line = line.replace(f"${n}", code)
        key, value = info[i] if i < len(info) else ("", "")
        text = f"{keys}{key}{reset}  {value}" if key else f"{title}{value}{reset}"
        print(line + reset + " " * (width - len(plain)) + text)
    print()


def main():
    if os.name == "nt":
        os.system("")  # turns on the ANSI colors in the Windows console
        sys.stdout.reconfigure(encoding="utf-8")
    cfg = config()
    if shutil.which("fastfetch") and with_fastfetch(cfg):
        return
    example(cfg)


if __name__ == "__main__":
    main()
