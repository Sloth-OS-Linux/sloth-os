"""The installer's data: the languages, keyboards, time zones and disks to choose from.

The list of languages comes from Sloth Welcome's translations: whatever the system speaks
on first start can be chosen here. The keyboard and the time zone follow from the language,
but can be changed.
"""
import json
import logging
import re
import subprocess
import zoneinfo
from pathlib import Path

from sloth_common.i18n import Catalog, sort_key

log = logging.getLogger("sloth-installer.system")

WELCOME_TRANSLATIONS = Path("/usr/lib/sloth-os/sloth-welcome/sloth_welcome/translations")
MIN_DISK_BYTES = 40 * 1024**3       # we do not install on a smaller disk
RECOMMENDED_BYTES = 120 * 1024**3   # recommended for games

# Language -> (locale, keyboard, time zone). The keyboard is an XKB name; for languages not written in Latin
# letters US comes first, so the user name and the password are in Latin letters
# (Alt+Shift switches), as in Fedora's installer.
LANGUAGES = {
    "af": ("af_ZA.UTF-8", "us", "Africa/Johannesburg"),
    "ar": ("ar_EG.UTF-8", "us,ara", "Africa/Cairo"),
    "as": ("as_IN.UTF-8", "us", "Asia/Kolkata"),
    "be": ("be_BY.UTF-8", "us,by", "Europe/Minsk"),
    "bg": ("bg_BG.UTF-8", "us,bg", "Europe/Sofia"),
    "bn_IN": ("bn_IN.UTF-8", "us", "Asia/Kolkata"),
    "ca": ("ca_ES.UTF-8", "es", "Europe/Madrid"),
    "cs": ("cs_CZ.UTF-8", "cz", "Europe/Prague"),
    "da": ("da_DK.UTF-8", "dk", "Europe/Copenhagen"),
    "de": ("de_DE.UTF-8", "de", "Europe/Berlin"),
    "el": ("el_GR.UTF-8", "us,gr", "Europe/Athens"),
    "en": ("en_US.UTF-8", "us", "America/New_York"),
    "eo": ("eo.UTF-8", "us", "UTC"),
    "es": ("es_ES.UTF-8", "es", "Europe/Madrid"),
    "et": ("et_EE.UTF-8", "ee", "Europe/Tallinn"),
    "fi": ("fi_FI.UTF-8", "fi", "Europe/Helsinki"),
    "fr": ("fr_FR.UTF-8", "fr", "Europe/Paris"),
    "fur": ("fur_IT.UTF-8", "it", "Europe/Rome"),
    "he": ("he_IL.UTF-8", "us,il", "Asia/Jerusalem"),
    "hr": ("hr_HR.UTF-8", "hr", "Europe/Zagreb"),
    "hu": ("hu_HU.UTF-8", "hu", "Europe/Budapest"),
    "ia": ("ia_FR.UTF-8", "us", "UTC"),
    "id": ("id_ID.UTF-8", "us", "Asia/Jakarta"),
    "it": ("it_IT.UTF-8", "it", "Europe/Rome"),
    "ja": ("ja_JP.UTF-8", "jp", "Asia/Tokyo"),
    "ka": ("ka_GE.UTF-8", "us,ge", "Asia/Tbilisi"),
    "kab": ("kab_DZ.UTF-8", "fr", "Africa/Algiers"),
    "kk": ("kk_KZ.UTF-8", "us,kz", "Asia/Almaty"),
    "ko": ("ko_KR.UTF-8", "kr", "Asia/Seoul"),
    "lo": ("lo_LA.UTF-8", "us,la", "Asia/Vientiane"),
    "lt": ("lt_LT.UTF-8", "lt", "Europe/Vilnius"),
    "nb": ("nb_NO.UTF-8", "no", "Europe/Oslo"),
    "nl": ("nl_NL.UTF-8", "us", "Europe/Amsterdam"),
    "nn": ("nn_NO.UTF-8", "no", "Europe/Oslo"),
    "pa": ("pa_IN.UTF-8", "us", "Asia/Kolkata"),
    "pl": ("pl_PL.UTF-8", "pl", "Europe/Warsaw"),
    "pt": ("pt_PT.UTF-8", "pt", "Europe/Lisbon"),
    "pt_BR": ("pt_BR.UTF-8", "br", "America/Sao_Paulo"),
    "ro": ("ro_RO.UTF-8", "ro", "Europe/Bucharest"),
    "ru": ("ru_RU.UTF-8", "us,ru", "Europe/Moscow"),
    "sk": ("sk_SK.UTF-8", "sk", "Europe/Bratislava"),
    "sl": ("sl_SI.UTF-8", "si", "Europe/Ljubljana"),
    "sq": ("sq_AL.UTF-8", "al", "Europe/Tirane"),
    "sr": ("sr_RS.UTF-8", "us,rs", "Europe/Belgrade"),
    "sv": ("sv_SE.UTF-8", "se", "Europe/Stockholm"),
    "ta": ("ta_IN.UTF-8", "us", "Asia/Kolkata"),
    "tr": ("tr_TR.UTF-8", "tr", "Europe/Istanbul"),
    "uk": ("uk_UA.UTF-8", "us,ua", "Europe/Kyiv"),
    "zh_CN": ("zh_CN.UTF-8", "cn", "Asia/Shanghai"),
    "zh_TW": ("zh_TW.UTF-8", "tw", "Asia/Taipei"),
}

# Keyboards to choose from: (XKB name, displayed name in the language's own name)
KEYBOARDS = [
    ("us", "English (US)"), ("gb", "English (UK)"), ("us(intl)", "English (US, international)"),
    ("hu", "Magyar"), ("de", "Deutsch"), ("ch", "Deutsch (Schweiz)"), ("fr", "Français"),
    ("be", "Français (Belgique)"), ("ca", "Français (Canada)"), ("es", "Español"),
    ("latam", "Español (Latinoamérica)"), ("it", "Italiano"), ("pt", "Português"),
    ("br", "Português (Brasil)"), ("nl", "Nederlands"), ("pl", "Polski"), ("cz", "Čeština"),
    ("sk", "Slovenčina"), ("si", "Slovenščina"), ("hr", "Hrvatski"), ("ro", "Română"),
    ("al", "Shqip"), ("tr", "Türkçe"), ("se", "Svenska"), ("no", "Norsk"), ("dk", "Dansk"),
    ("fi", "Suomi"), ("ee", "Eesti"), ("lt", "Lietuvių"), ("lv", "Latviešu"),
    ("us,ru", "Русский"), ("us,ua", "Українська"), ("us,by", "Беларуская"), ("us,bg", "Български"),
    ("us,rs", "Српски"), ("us,kz", "Қазақ"), ("us,gr", "Ελληνικά"), ("us,il", "עברית"),
    ("us,ara", "العربية"), ("us,ge", "ქართული"), ("us,la", "ລາວ"), ("jp", "日本語"), ("kr", "한국어"),
    ("cn", "中文"), ("tw", "中文 (台灣)"),
]


def languages():
    """[{"code", "name", "locale", "keyboard", "timezone"}] from Sloth Welcome's languages."""
    out = []
    for lang in Catalog(WELCOME_TRANSLATIONS).available():
        locale, kbd, tz = LANGUAGES.get(lang["code"], ("en_US.UTF-8", "us", "UTC"))
        out.append({**lang, "locale": locale, "keyboard": kbd, "timezone": tz})
    return out


def keyboards():
    return [{"id": k, "name": n} for k, n in sorted(KEYBOARDS, key=lambda x: sort_key(x[1]))]


def timezones():
    """The time zones in region/city form ("Europe/Budapest"), plus UTC."""
    regions = ("Africa", "America", "Antarctica", "Asia", "Atlantic", "Australia", "Europe", "Indian", "Pacific")
    zones = sorted(z for z in zoneinfo.available_timezones() if z.split("/")[0] in regions)
    return [{"id": z, "name": z.replace("_", " ").replace("/", " / ")} for z in zones] + [{"id": "UTC", "name": "UTC"}]


def apply_live_keyboard(kbd):
    """The chosen layout in the live session too: in the test field one can already type with the new layout.

    KWin switches right away on the change notification of ~/.config/kxkbrc (kwriteconfig6 --notify).
    """
    layouts, variants = [], []
    for item in kbd.split(","):
        layout, _, variant = item.partition("(")
        layouts.append(layout)
        variants.append(variant.rstrip(")"))
    settings = {"LayoutList": ",".join(layouts), "VariantList": ",".join(variants), "Use": "true",
                "Options": "grp:alt_shift_toggle" if len(layouts) > 1 else "", "ResetOldOptions": "true"}
    try:
        for key, value in settings.items():
            subprocess.run(["kwriteconfig6", "--file", "kxkbrc", "--group", "Layout", "--key", key,
                            "--notify", value], check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("keyboard (live): %s", e)


def apply_live_language(code, locale):
    """The chosen language on the live desktop too (after "Try Sloth OS").

    Besides Plasma's language setting (plasma-localerc) the session's environment switches too, then
    the desktop (plasmashell) restarts: the taskbar, the menu and the apps started from there come up in the
    chosen language. No need to sign out (the liveuser's automatic login only works once).
    """
    language = code if code.startswith("en") else f"{code}:en_US"
    try:
        for group, key, value in (("Translations", "LANGUAGE", language), ("Formats", "LANG", locale)):
            subprocess.run(["kwriteconfig6", "--file", "plasma-localerc", "--group", group, "--key", key, value],
                           check=True, timeout=10)
        subprocess.run(["dbus-update-activation-environment", "--systemd",
                        f"LANG={locale}", f"LANGUAGE={language}"], check=True, timeout=10)
        subprocess.Popen(["systemctl", "--user", "restart", "plasma-plasmashell.service"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("language (live): %s", e)


# --- Screens ----------------------------------------------------------------------

def set_primary_display(name):
    """Makes the screen the main one in the live session too (KScreen: the panel and new windows go there)."""
    if not re.fullmatch(r"[A-Za-z0-9-]{1,32}", name or ""):
        return False
    try:
        return subprocess.run(["kscreen-doctor", f"output.{name}.priority.1"], capture_output=True,
                              timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# --- Lemezek ----------------------------------------------------------------------

def _lsblk():
    out = subprocess.run(
        ["lsblk", "--json", "--bytes", "--output",
         "NAME,PATH,SIZE,TYPE,RO,RM,ROTA,TRAN,MODEL,VENDOR,FSTYPE,LABEL,PARTLABEL,MOUNTPOINTS"],
        capture_output=True, text=True, check=True, timeout=20).stdout
    return json.loads(out).get("blockdevices", [])


def _live_disks():
    """The disks (e.g. the USB stick) the live system runs from: we cannot install on them.

    The whole chain of devices is followed upwards (`lsblk -s`): with Ventoy the live system's source is a
    device-mapper device (/dev/mapper/ventoy) on a partition of the stick, not the partition itself."""
    try:
        src = subprocess.run(["findmnt", "--noheadings", "--output", "SOURCE", "/run/initramfs/live"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if not src:
            return set()
        out = subprocess.run(["lsblk", "--inverse", "--noheadings", "--raw", "--output", "PATH,TYPE", src],
                             capture_output=True, text=True, timeout=10).stdout
        return {path for path, kind in (line.split()[:2] for line in out.splitlines() if line.strip())
                if kind == "disk"} or {src}
    except (OSError, subprocess.SubprocessError, ValueError):
        return set()


def _contents(disk):
    """What is on the disk now: "windows", "linux", "other" or "empty", and the partitions' names."""
    # The file system may also be directly on the disk, without a partition table
    parts = (disk.get("children") or []) + ([disk] if disk.get("fstype") else [])
    fstypes = {(p.get("fstype") or "").lower() for p in parts}
    names = [p.get("label") or p.get("partlabel") for p in parts if p.get("label") or p.get("partlabel")]
    if not parts:
        kind = "empty"
    elif fstypes & {"ntfs", "bitlocker"}:
        kind = "windows"
    elif fstypes & {"ext4", "btrfs", "xfs", "crypto_luks"}:
        kind = "linux"
    else:
        kind = "other"
    return kind, names


def _disk_name(d):
    """The disk's vendor and model (e.g. "Samsung SSD 980"); if there is none, the device name (e.g. "sda").
    For virtual machines' disks the "vendor" is only an ID (e.g. "0x1af4"); we do not show it.
    """
    vendor = (d.get("vendor") or "").strip()
    if re.fullmatch(r"0x[0-9a-fA-F]+", vendor):
        vendor = ""
    name = " ".join(" ".join(x for x in (vendor, d.get("model")) if x).split())
    return name or d.get("name", "")


def _disk_kind(d):
    """The kind of drive: "nvme", "ssd", "hdd" or "usb" (the UI translates it: disk.kind.*)."""
    tran = (d.get("tran") or "").lower()
    if tran == "usb":
        return "usb"
    if tran == "nvme" or d.get("name", "").startswith("nvme"):
        return "nvme"
    return "hdd" if d.get("rota") else "ssd"


def disks():
    """The disks that can be installed to, with a human description. Too small ones are shown disabled."""
    live = _live_disks()
    out = []
    for d in _lsblk():
        if d.get("type") != "disk" or d.get("ro") or d.get("name", "").startswith(("zram", "loop", "sr")):
            continue
        if d.get("path") in live:
            continue
        kind, names = _contents(d)
        size = int(d.get("size") or 0)
        parts = (d.get("children") or []) + ([d] if d.get("fstype") else [])
        out.append({
            "path": d["path"],
            "model": _disk_name(d),
            "kind": _disk_kind(d),
            "size": size,
            "sizeText": f"{size / 1000**3:.0f} GB",
            "transport": (d.get("tran") or "").lower(),   # nvme, sata, usb…
            "removable": bool(d.get("rm")) or (d.get("tran") or "").lower() == "usb",
            "contents": kind,
            # Linux file systems that can be used as they are, if it is not the install target ("keep")
            "linuxParts": [{"path": p["path"], "fstype": (p.get("fstype") or "").lower(),
                            "label": p.get("label") or p.get("partlabel") or p.get("name", ""),
                            "sizeText": f"{int(p.get('size') or 0) / 1000**3:.0f} GB"}
                           for p in parts if (p.get("fstype") or "").lower() in ("ext4", "btrfs", "xfs")],
            "partitionNames": names[:4],
            "tooSmall": size < MIN_DISK_BYTES,
            "small": size < RECOMMENDED_BYTES,
        })
    return out


# --- Checking the computer before anything is done (the first page) ----------------------------------------------

# The checks' ids; the texts are "check.<id>" in the translations
CHECKS = ("bios", "memory", "battery", "secureboot_nvidia")
SECURE_BOOT_VAR = "efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-e39e1b2c9b4b"
MIN_MEMORY_BYTES = 3584 * 1024**2   # "4 GB": a 4 GB computer reports a little less, some is kept by the hardware


def _read(path, binary=False):
    try:
        return Path(path).read_bytes() if binary else Path(path).read_text(errors="replace").strip()
    except OSError:
        return b"" if binary else ""


def secure_boot_on(firmware="/sys/firmware/efi"):
    """The SecureBoot variable: 4 bytes of attributes, then 1 = on."""
    data = _read(Path(firmware) / SECURE_BOOT_VAR, binary=True)
    return len(data) >= 5 and data[4] == 1


def has_nvidia(pci="/sys/bus/pci/devices"):
    """An NVIDIA graphics card (vendor 0x10de, display controller class 0x03…)."""
    try:
        devices = list(Path(pci).iterdir())
    except OSError:
        return False
    return any(_read(d / "vendor") == "0x10de" and _read(d / "class").startswith("0x03") for d in devices)


def on_battery(power="/sys/class/power_supply"):
    """A battery and no charger plugged in."""
    try:
        supplies = list(Path(power).iterdir())
    except OSError:
        return False
    battery = any(_read(s / "type") == "Battery" and _read(s / "scope") != "Device" for s in supplies)
    plugged = any(_read(s / "type") in ("Mains", "USB", "USB_C", "USB_PD") and _read(s / "online") == "1"
                  for s in supplies)
    return battery and not plugged


def memory_bytes(meminfo="/proc/meminfo"):
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", _read(meminfo), re.M)
    return int(m.group(1)) * 1024 if m else 0


def machine_check(firmware="/sys/firmware/efi", pci="/sys/bus/pci/devices", power="/sys/class/power_supply",
                  meminfo="/proc/meminfo"):
    """What to know about this computer before installing: [{"id", "level"}], level "block" (cannot install),
    "warn" or "info". The texts are "check.<id>" in the translations. Nothing here touches a disk."""
    out = []
    if not Path(firmware).is_dir():
        # Sloth OS boots with UEFI only; in legacy (BIOS) mode the installed system would not start
        out.append({"id": "bios", "level": "block"})
    memory = memory_bytes(meminfo)
    if memory and memory < MIN_MEMORY_BYTES:
        out.append({"id": "memory", "level": "warn"})
    if on_battery(power):
        out.append({"id": "battery", "level": "warn"})
    if secure_boot_on(firmware) and has_nvidia(pci):
        out.append({"id": "secureboot_nvidia", "level": "info"})
    return out
