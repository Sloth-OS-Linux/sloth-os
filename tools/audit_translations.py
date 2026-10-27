#!/usr/bin/env python3
"""A quality check of the translations, beyond tools/check_translations.py (developer tool, not in the image).

check_translations.py says whether a key is missing; this one looks at the texts themselves:
  - placeholders ({name}, {size}…) that differ from the English text,
  - empty or punctuation-only texts,
  - longer texts left in English,
  - texts in the wrong script (only Latin text in a Cyrillic, Greek, Arabic, CJK… language, or the other way round),
  - texts much shorter or longer than the English one (often a text that belongs to another key).

Usage: python tools/audit_translations.py [language…]      (exits with 1 if it found anything)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = {
    "sloth-center": REPO / "files/system/usr/lib/sloth-os/sloth-center/sloth_center/translations",
    "sloth-welcome": REPO / "files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome/translations",
    "sloth-exe": REPO / "files/system/usr/lib/sloth-os/sloth-exe/sloth_exe/translations",
    "sloth-installer": REPO / "iso/files/usr/lib/sloth-os/sloth-installer/sloth_installer/translations",
}
EN_KEYED = {"sloth-center"}
# Languages not written in the Latin script: their texts should be mostly in their own script
NON_LATIN = {"ar", "as", "be", "bg", "bn_IN", "el", "he", "ja", "ka", "kk", "ko", "lo", "pa", "ru", "sr", "ta",
             "uk", "zh_CN", "zh_TW"}
# Words that stay as they are in every language (brands, technical names)
KEEP = re.compile(r"(?i)\b(sloth|os|windows|linux|steam|proton|wine|flatpak|flathub|discover|dolphin|konsole|kde|"
                  r"plasma|wi-?fi|ethernet|bluetooth|usb|uefi|bios|secure boot|nvidia|amd|intel|gpu|cpu|ssd|hdd|"
                  r"nvme|btrfs|ext4|ntfs|exfat|fat32|iso|exe|msi|appimage|deb|rpm|dvd|pin|tpm|vpn|dns|ping|ms|gb|mb|"
                  r"tb|kb|hz|fps|hdr|vrr|ko-fi|github|sourceforge|battle\.net|ea|epic|gog|ubisoft|heroic|lutris|"
                  r"bottles|firefox|chrome|libreoffice|feedback|ok|id|url|api|vulkan|directx|dxvk|"
                  r"\{[a-z_]+\}|[A-Z]:\\|https?://\S+)\b")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
# Checked by hand and right as they are (a short exclamation, a script that packs more into a character…)
KNOWN_OK = {
    ("sloth-center", "he", "Are you sure you want to reset this PC?"),
    ("sloth-center", "ja", "Secure Boot is on."),
    ("sloth-center", "ko", "Secure Boot is on."),
    ("sloth-welcome", "he", "done.start"),
    ("sloth-welcome", "kab", "done.start"),
    ("sloth-welcome", "zh_CN", "app.org.kde.krita"),
    ("sloth-welcome", "zh_TW", "app.org.kde.krita"),
    ("sloth-exe", "lt", "pick.done_title"),
    ("sloth-installer", "lt", "done.heading"),
}


def scripts(text):
    """How many letters of the text are Latin and how many are not."""
    latin = other = 0
    for ch in KEEP.sub(" ", PLACEHOLDER.sub(" ", text)):
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, "")
        if name.startswith("LATIN"):
            latin += 1
        else:
            other += 1
    return latin, other


def audit(only):
    problems = 0
    for tool, folder in TOOLS.items():
        en = json.loads((folder / "en.json").read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.json")):
            lang = path.stem
            if lang == "en" or (only and lang not in only):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if key.startswith("_") or not isinstance(value, str) or (tool, lang, key) in KNOWN_OK:
                    continue
                source = key if tool in EN_KEYED else en.get(key)
                if source is None:
                    continue
                found = []
                if set(PLACEHOLDER.findall(value)) != set(PLACEHOLDER.findall(source)):
                    found.append("placeholders differ")
                if not re.search(r"\w", value):
                    found.append("empty")
                plain = KEEP.sub("", source).strip()
                if value == source and len(re.findall(r"[A-Za-z]{3,}", plain)) >= 3 and lang != "en":
                    found.append("left in English")
                latin, other = scripts(value)
                if lang in NON_LATIN and latin > 12 and other == 0:
                    found.append("only Latin text in a non-Latin language")
                if lang not in NON_LATIN and other > 3 and other > latin:
                    found.append("non-Latin text in a Latin language")
                # CJK packs more into a character; other scripts are compared by length as is
                ratio = len(value) / max(1, len(source)) * (2.5 if lang in ("ja", "zh_CN", "zh_TW", "ko") else 1)
                if len(source) >= 15 and not 0.4 <= ratio <= 3.0:
                    found.append(f"length differs a lot ({ratio:.1f}x)")
                for what in found:
                    problems += 1
                    print(f"{tool} {lang}: {what}: {key[:60]!r} = {value[:80]!r}")
    return problems


if __name__ == "__main__":
    n = audit(set(sys.argv[1:]))
    print(f"{n} problem(s)." if n else "No problems found.")
    sys.exit(1 if n else 0)
