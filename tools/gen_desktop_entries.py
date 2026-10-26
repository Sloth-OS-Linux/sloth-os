#!/usr/bin/env python3
"""Start menu entries (.desktop) of Sloth OS's own tools, generated from the translation files (developer tool).

Do not edit the .desktop files by hand: the names, descriptions and keywords live in the tools'
translations/<language>.json files, and this script writes all 50 languages from them.
The default (language-less) text is English, so an unknown language shows English too.

Usage: python tools/gen_desktop_entries.py           (rewrite the files)
       python tools/gen_desktop_entries.py --check   (check only; exits with 1 if something is out of date)
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "files/system/usr/lib/sloth-os"
TRANSLATIONS = {
    "sloth-welcome": TOOLS / "sloth-welcome/sloth_welcome/translations",
    "sloth-center": TOOLS / "sloth-center/sloth_center/translations",
    "sloth-exe": TOOLS / "sloth-exe/sloth_exe/translations",
    "sloth-installer": REPO / "iso/files/usr/lib/sloth-os/sloth-installer/sloth_installer/translations",
}
# In Sloth Center's translations the English text is the key (its en.json only has the language name)
EN_KEYED = {"sloth-center"}

# File -> fields. A translated field's value is (tool, key); everything else is written as is.
ENTRIES = {
    "files/system/usr/share/applications/org.slothos.welcome.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-welcome", "app.title")),
        ("GenericName", ("sloth-welcome", "desktop.generic")),
        ("Comment", ("sloth-welcome", "desktop.comment")),
        ("Exec", "sloth-welcome"),
        ("Icon", "sloth-os"),
        ("Terminal", "false"),
        ("Categories", "Settings;"),
        ("Keywords", ("sloth-welcome", "desktop.keywords")),
        ("StartupNotify", "true"),
    ],
    "files/system/etc/xdg/autostart/org.slothos.welcome-autostart.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-welcome", "app.title")),
        ("Exec", "sloth-welcome --first-run"),
        ("Icon", "sloth-os"),
        ("Terminal", "false"),
        ("NoDisplay", "true"),
        ("X-KDE-autostart-phase", "2"),
        ("OnlyShowIn", "KDE;"),
    ],
    # First sign-in: the main screen chosen in the installer (/usr/libexec/sloth-os/display-setup)
    "files/system/etc/xdg/autostart/org.slothos.display-setup.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-installer", "welcome.screen")),
        ("Exec", "/usr/libexec/sloth-os/display-setup"),
        ("Icon", "video-display"),
        ("Terminal", "false"),
        ("NoDisplay", "true"),
        ("X-KDE-autostart-phase", "1"),
        ("OnlyShowIn", "KDE;"),
    ],
    "files/system/usr/share/applications/org.slothos.center.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-center", "Sloth Center")),
        ("GenericName", ("sloth-center", "System settings")),
        ("Comment", ("sloth-center", "Updates, rollback, drivers and everything that would otherwise need a terminal")),
        ("Exec", "sloth-center"),
        ("Icon", "sloth-center"),
        ("Terminal", "false"),
        ("Categories", "Settings;"),
        ("Keywords", ("sloth-center", "update;rollback;driver;settings")),
        ("StartupNotify", "true"),
    ],
    "files/system/usr/share/applications/org.slothos.exe.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-exe", "desktop.name")),
        ("Comment", ("sloth-exe", "desktop.comment")),
        ("Exec", "sloth-exe %f"),
        ("Icon", "application-x-ms-dos-executable"),
        ("Terminal", "false"),
        ("NoDisplay", "true"),
        ("MimeType", "application/x-ms-dos-executable;application/x-msdownload;application/x-msi;"
                     "application/x-ms-installer;application/vnd.microsoft.portable-executable;application/x-dosexec;"
                     # Linux packages (AppImage, .deb, .rpm) and Mac files (a clear message)
                     "application/vnd.appimage;application/x-iso9660-appimage;application/vnd.debian.binary-package;application/x-deb;application/x-rpm;application/x-redhat-package-manager;application/x-apple-diskimage;application/x-xar;"
                     # disc images (.iso): mounted with a double-click, the installer on them offered
                     "application/x-cd-image;application/x-iso9660-image;"),
        ("Categories", "Utility;"),
    ],
    # Dolphin, right-click on a file or folder (on a folder's empty area: that folder): Previous versions
    "files/system/usr/share/kio/servicemenus/org.slothos.versions.desktop": [
        ("Type", "Service"),
        ("X-KDE-ServiceTypes", "KonqPopupMenu/Plugin"),
        ("MimeType", "all/all;"),
        ("X-KDE-Protocols", "file"),
        ("X-KDE-RequiredNumberOfUrls", "1"),
        ("X-KDE-Priority", "TopLevel"),
        ("Actions", "previousVersions;"),
        ("[Desktop Action previousVersions]", None),
        ("Name", ("sloth-center", "Previous versions")),
        ("Icon", "view-history"),
        ("Exec", "sloth-versions %f"),
    ],
    "iso/files/usr/share/applications/org.slothos.installer.desktop": [
        ("Type", "Application"),
        ("Name", ("sloth-installer", "app.title")),
        ("Comment", ("sloth-installer", "desktop.comment")),
        ("Exec", "sloth-installer"),
        ("Icon", "sloth-os"),
        ("Terminal", "false"),
        ("Categories", "System;"),
        ("Keywords", ("sloth-installer", "desktop.keywords")),
        ("StartupNotify", "true"),
    ],
}


def load(tool):
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TRANSLATIONS[tool].glob("*.json"))}


def text(langs, tool, lang, key):
    if tool in EN_KEYED and lang == "en":
        return key
    return langs.get(lang, {}).get(key)


def keywords(local, english):
    """The local keywords, followed by the English ones (so it can be found in English too)."""
    words = []
    for w in (local or "").split(";") + english.split(";"):
        w = w.strip()
        if w and w not in words:
            words.append(w)
    return ";".join(words) + ";"


def render(path, fields, cache):
    lines = ["# Generated by tools/gen_desktop_entries.py from the tools' translations/*.json - do not edit by hand.",
             "[Desktop Entry]"]
    for name, value in fields:
        if value is None:  # a new section (e.g. [Desktop Action …])
            lines.append(name)
            continue
        if isinstance(value, str):
            lines.append(f"{name}={value}")
            continue
        tool, key = value
        langs = cache.setdefault(tool, load(tool))
        all_langs = sorted(langs)
        english = text(langs, tool, "en", key)
        if not english:
            sys.exit(f"{path}: missing English text: {tool} / {key}")
        lines.append(f"{name}={keywords(None, english) if name == 'Keywords' else english}")
        for lang in all_langs:
            local = text(langs, tool, lang, key)
            if lang == "en" or not local:
                continue
            lines.append(f"{name}[{lang}]={keywords(local, english) if name == 'Keywords' else local}")
    return "\n".join(lines) + "\n"


def main():
    check = "--check" in sys.argv[1:]
    cache, stale = {}, []
    for rel, fields in ENTRIES.items():
        path = REPO / rel
        content = render(rel, fields, cache)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        stale.append(rel)
        if not check:
            path.write_bytes(content.encode("utf-8"))  # LF line endings on Windows too
    if check and stale:
        print("Out-of-date .desktop files (run: python tools/gen_desktop_entries.py):", *stale, sep="\n  ")
        return 1
    print(("Updated:" if stale else "Everything is up to date."), *stale, sep="\n  " if stale else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
