"""Driver options (Sloth Center → Advanced settings): the graphical way to `options <driver> …` and `blacklist <driver>`
in /etc/modprobe.d, which some hardware needs to work well (a Wi-Fi card that keeps dropping, a driver that has to
stay off). Before this, only a terminal could do it (GitHub issue: a Lite-On / Realtek Wi-Fi card, 2026-11).

Two ways in:
- Known fixes for this computer (KNOWN_FIXES): offered only when the driver is in use here (/sys/module), with one
  button, in plain words; e.g. a Realtek Wi-Fi card's power saving off (ips=0 fwlps=0).
- Your own (for a guide's advice): a driver's option, or the driver turned off. Only an existing driver and its real
  parameters (modinfo) are taken, and the drivers the computer cannot start without (disks, file systems, USB
  keyboards, disk encryption) cannot be turned off.
Everything takes effect after a restart. The helper (sloth-helper driver-options) writes both files:
  /etc/sloth-os/driver-options.json   what was chosen (readable by everyone: Sloth Center shows it)
  /etc/modprobe.d/sloth-user.conf     what the kernel reads
"""
import json
import os
import re
import subprocess
from pathlib import Path

STATE = Path(os.environ.get("SLOTH_DRIVER_OPTIONS", "/etc/sloth-os/driver-options.json"))
CONF = Path(os.environ.get("SLOTH_DRIVER_CONF", "/etc/modprobe.d/sloth-user.conf"))
SYS_MODULE = Path(os.environ.get("SLOTH_SYS_MODULE", "/sys/module"))

MODULE_RE = re.compile(r"^[a-z0-9_]{2,40}$")
PARAM_RE = re.compile(r"^[a-z0-9_]{1,40}$")
VALUE_RE = re.compile(r"^[A-Za-z0-9_.,:-]{1,64}$")
# The computer does not start (or cannot be used) without these: they cannot be turned off here
PROTECTED = re.compile(r"^(nvme|nvme_core|ahci|libahci|sd_mod|sr_mod|scsi_mod|virtio\w*|xhci_\w+|ehci_\w+|ohci_\w+|"
                       r"uhci_\w+|usb_storage|uas|usbhid|hid|hid_generic|hid_\w+|i2c_hid\w*|btrfs|ext4|xfs|vfat|fat|"
                       r"dm_crypt|dm_mod|md_mod|raid\w+|loop|overlay|squashfs|erofs|efivarfs|crc32c\w*|"
                       r"atkbd|i8042|serio\w*|psmouse|evdev|drm|drm_kms_helper)$")

# Known fixes: (id, the drivers it is for, the options, the text). Offered when one of the drivers is in use here.
KNOWN_FIXES = [
    {"id": "realtek-wifi-power",
     "modules": ["rtl8188ee", "rtl8192ce", "rtl8192cu", "rtl8192de", "rtl8192se", "rtl8723ae", "rtl8723be",
                 "rtl8821ae"],
     "options": {"ips": "0", "fwlps": "0"},
     "text": "Wi-Fi keeps dropping: turn off the Realtek Wi-Fi card's power saving ({module})"},
    {"id": "realtek-rtw88-aspm", "modules": ["rtw88_pci"], "options": {"disable_aspm": "1"},
     "text": "Wi-Fi keeps dropping or is slow: turn off the Realtek Wi-Fi card's link power saving ({module})"},
    {"id": "realtek-rtw89-aspm", "modules": ["rtw89_pci"], "options": {"disable_aspm_l1": "1", "disable_aspm_l1ss": "1"},
     "text": "Wi-Fi keeps dropping or is slow: turn off the Realtek Wi-Fi card's link power saving ({module})"},
    {"id": "mediatek-mt7921-aspm", "modules": ["mt7921e"], "options": {"disable_aspm": "1"},
     "text": "Wi-Fi keeps dropping: turn off the MediaTek Wi-Fi card's link power saving ({module})"},
]


def load():
    """What was chosen: [{"module", "options": {param: value}, "off": bool, "fix": id or ""}]."""
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return [e for e in entries or [] if isinstance(e, dict) and MODULE_RE.match(str(e.get("module", "")))]


def render(entries):
    """The modprobe.d file for the entries."""
    lines = ["# Sloth OS: driver options chosen in Sloth Center → Advanced settings (sloth_common/driver_options.py).",
             "# Edited there; changes here are overwritten."]
    for e in entries:
        if e.get("off"):
            lines.append(f"blacklist {e['module']}")
        elif e.get("options"):
            lines.append(f"options {e['module']} " + " ".join(f"{k}={v}" for k, v in sorted(e["options"].items())))
    return "\n".join(lines) + "\n"


def parse_options(text):
    """ "ips=0 fwlps=0" -> {"ips": "0", "fwlps": "0"}, or None if any part is not param=value."""
    out = {}
    for token in text.split():
        name, sep, value = token.partition("=")
        if not sep or not PARAM_RE.match(name) or not VALUE_RE.match(value):
            return None
        out[name] = value
    return out or None


def module_params(module, modinfo="modinfo"):
    """The parameters a driver really has (modinfo -p), or None if there is no such driver."""
    try:
        r = subprocess.run([modinfo, "-p", module], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {line.split(":", 1)[0].strip() for line in r.stdout.splitlines() if ":" in line}


def check(entries, modinfo="modinfo"):
    """None if every entry is fine, else the first problem: "module" (no such driver), "param" (it has no such
    option), "protected" (the computer needs it), "empty"."""
    for e in entries:
        module = str(e.get("module", ""))
        if not MODULE_RE.match(module):
            return "module"
        if e.get("off"):
            if PROTECTED.match(module):
                return "protected"
            if module_params(module, modinfo) is None:
                return "module"
            continue
        options = e.get("options") or {}
        if not isinstance(options, dict) or not options:
            return "empty"
        params = module_params(module, modinfo)
        if params is None:
            return "module"
        for k, v in options.items():
            if not PARAM_RE.match(str(k)) or not VALUE_RE.match(str(v)) or k not in params:
                return "param"
    return None


def in_use(module):
    return (SYS_MODULE / module).is_dir()


def suggestions(entries=None):
    """The known fixes for the drivers in use here that are not applied yet: [{"id", "module", "options", "text"}]
    (text: the English sentence, translated by the caller)."""
    entries = load() if entries is None else entries
    chosen = {e["module"] for e in entries}
    out = []
    for fix in KNOWN_FIXES:
        for module in fix["modules"]:
            if in_use(module) and module not in chosen:
                out.append({"id": fix["id"], "module": module, "options": dict(fix["options"]), "text": fix["text"]})
    return out


def fix_entry(fix_id, module):
    """The entry for a known fix on one of its drivers, or None."""
    for fix in KNOWN_FIXES:
        if fix["id"] == fix_id and module in fix["modules"]:
            return {"module": module, "options": dict(fix["options"]), "off": False, "fix": fix_id}
    return None
