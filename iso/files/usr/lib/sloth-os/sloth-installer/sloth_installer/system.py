"""A telepítő adatai: választható nyelvek, billentyűzetek, időzónák és lemezek.

A nyelvek listája a Sloth Üdvözlő fordításaiból jön: amit a rendszer első indításkor
beszél, azt lehet itt választani. A billentyűzet és az időzóna a nyelvből adódik,
de átállítható.
"""
import json
import logging
import subprocess
import zoneinfo
from pathlib import Path

from sloth_common.i18n import Catalog, sort_key

log = logging.getLogger("sloth-installer.system")

WELCOME_TRANSLATIONS = Path("/usr/lib/sloth-os/sloth-welcome/sloth_welcome/translations")
MIN_DISK_BYTES = 40 * 1024**3       # ennél kisebb lemezre nem telepítünk
RECOMMENDED_BYTES = 120 * 1024**3   # játékokhoz ennyi ajánlott

# Nyelv -> (locale, billentyűzet, időzóna). A billentyűzet XKB-név; nem latin betűs
# nyelveknél az amerikai az első, hogy a felhasználónév és a jelszó latin betűs legyen
# (Alt+Shift vált), mint a Fedora telepítőjében.
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

# Választható billentyűzetek: (XKB-név, megjelenített név a nyelv saját nevével)
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
    """[{"code", "name", "locale", "keyboard", "timezone"}] a Sloth Üdvözlő nyelvei közül."""
    out = []
    for lang in Catalog(WELCOME_TRANSLATIONS).available():
        locale, kbd, tz = LANGUAGES.get(lang["code"], ("en_US.UTF-8", "us", "UTC"))
        out.append({**lang, "locale": locale, "keyboard": kbd, "timezone": tz})
    return out


def keyboards():
    return [{"id": k, "name": n} for k, n in sorted(KEYBOARDS, key=lambda x: sort_key(x[1]))]


def timezones():
    """Az időzónák régió/város formában ("Europe/Budapest"), plusz UTC."""
    regions = ("Africa", "America", "Antarctica", "Asia", "Atlantic", "Australia", "Europe", "Indian", "Pacific")
    zones = sorted(z for z in zoneinfo.available_timezones() if z.split("/")[0] in regions)
    return [{"id": z, "name": z.replace("_", " ").replace("/", " / ")} for z in zones] + [{"id": "UTC", "name": "UTC"}]


# --- Lemezek ----------------------------------------------------------------------

def _lsblk():
    out = subprocess.run(
        ["lsblk", "--json", "--bytes", "--output",
         "NAME,PATH,SIZE,TYPE,RO,RM,TRAN,MODEL,VENDOR,FSTYPE,LABEL,PARTLABEL,MOUNTPOINTS"],
        capture_output=True, text=True, check=True, timeout=20).stdout
    return json.loads(out).get("blockdevices", [])


def _live_disk():
    """Az a lemez (pl. a pendrive), amiről az élő rendszer fut: erre nem telepíthetünk."""
    try:
        src = subprocess.run(["findmnt", "--noheadings", "--output", "SOURCE", "/run/initramfs/live"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if not src:
            return None
        parent = subprocess.run(["lsblk", "--noheadings", "--nodeps", "--output", "PKNAME", src],
                                capture_output=True, text=True, timeout=10).stdout.strip()
        return f"/dev/{parent}" if parent else src
    except (OSError, subprocess.SubprocessError):
        return None


def _contents(disk):
    """Mi van most a lemezen: "windows", "linux", "other" vagy "empty", és a partíciók nevei."""
    # A fájlrendszer lehet közvetlenül a lemezen is, partíciós tábla nélkül
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


def disks():
    """A telepítésre szóba jövő lemezek, emberi leírással. A túl kicsiket letiltva mutatjuk."""
    live = _live_disk()
    out = []
    for d in _lsblk():
        if d.get("type") != "disk" or d.get("ro") or d.get("name", "").startswith(("zram", "loop", "sr")):
            continue
        if live and d.get("path") == live:
            continue
        kind, names = _contents(d)
        size = int(d.get("size") or 0)
        model = " ".join(x for x in (d.get("vendor"), d.get("model")) if x).strip() or d.get("name")
        out.append({
            "path": d["path"],
            "model": " ".join(model.split()),
            "size": size,
            "sizeText": f"{size / 1000**3:.0f} GB",
            "transport": (d.get("tran") or "").lower(),   # nvme, sata, usb…
            "removable": bool(d.get("rm")) or (d.get("tran") or "").lower() == "usb",
            "contents": kind,
            "partitionNames": names[:4],
            "tooSmall": size < MIN_DISK_BYTES,
            "small": size < RECOMMENDED_BYTES,
        })
    return out
