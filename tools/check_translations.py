#!/usr/bin/env python3
"""A Sloth OS saját eszközeinek (Üdvözlő, telepítő, .exe kezelő) fordításait ellenőrzi (fejlesztői segéd, nem kerül az image-be).

Megnézi, hogy:
  - a kódban és a katalógusban használt összes kulcs megvan-e a magyar (forrás) fájlban,
  - a többi nyelvből mi hiányzik (ezeknél az angol, végül a magyar szöveg látszik),
  - nincs-e felesleges kulcs, és a {helyőrzők} egyeznek-e a magyarral,
  - nincs-e olyan szó, amiben keveredik a latin, cirill vagy görög betű (elírás, pl. „Meglено”),
  - nincs-e benne láthatatlan karakter (feltételes elválasztó, nulla szélességű szóköz).

Használat: python tools/check_translations.py   (hiba esetén 1-gyel lép ki)
"""
import ast
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WELCOME = REPO / "files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome"
INSTALLER = REPO / "iso/files/usr/lib/sloth-os/sloth-installer/sloth_installer"
INSTALL_HELPER = REPO / "iso/files/usr/libexec/sloth-os/sloth-install-helper"
EXE = REPO / "files/system/usr/lib/sloth-os/sloth-exe/sloth_exe"
SOURCE = "hu"

# tr("…") a Pythonban, t("…") a QML-ben, valamint a kulcsként tárolt szövegek ("error.…", "done.…", "account.error.…")
KEY_PATTERN = re.compile(r'\b(?:tr|t)\(\s*"([a-z_]+\.[\w.]*\w)"|"((?:error|done|account\.error)\.[a-z_]+)"')
# QML-ben feltételes kulcsok: root.t(x ? "a.b" : "c.d")
CONDITIONAL_PATTERN = re.compile(r'root\.t\(([^()]*\?[^()]*)')
INVISIBLE = re.compile(r"[­​﻿]")  # feltételes elválasztó, nulla szélességű szóköz, BOM


def desktop_keys():
    """A start menü bejegyzéseinek kulcsai eszközönként (tools/gen_desktop_entries.py írja belőlük a .desktop fájlokat)."""
    keys = {}
    for fields in literal(REPO / "tools/gen_desktop_entries.py", "ENTRIES").values():
        for _name, value in fields:
            if isinstance(value, tuple):
                keys.setdefault(value[0], set()).add(value[1])
    return keys


def literal(path, name):
    """Egy modulszintű lista értéke a forrásból (importálás nélkül, mert a gi itt nincs meg)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def welcome_keys():
    """A Sloth Üdvözlő adatokból képzett kulcsai (katalógus, színtémák, elrendezések)."""
    keys = set()
    for cat in literal(WELCOME / "catalog.py", "CATEGORIES"):
        keys |= {f"category.{cat['id']}.name", f"category.{cat['id']}.hint"}
        keys |= {f"app.{a['id']}" for a in cat["apps"]}
    keys |= {f"scheme.{s['id']}" for s in literal(WELCOME / "desktop.py", "COLOR_SCHEMES")}
    for l in literal(WELCOME / "desktop.py", "LAYOUTS"):
        keys |= {f"layout.{l['id']}.name", f"layout.{l['id']}.description"}
    return keys | DESKTOP_KEYS["sloth-welcome"]


def installer_keys():
    """A telepítő futás közben képzett kulcsai: lépések (a segéd küldi) és a lemez tartalma."""
    stages = {stage for _keys, stage, _pct in literal(INSTALL_HELPER, "STAGES")}
    keys = {f"stage.{s}" for s in stages | {"start", "partition", "configure"}}
    return keys | {f"disk.contents.{c}" for c in ("empty", "windows", "linux", "other")} | DESKTOP_KEYS["sloth-installer"]


def exe_keys():
    """Az .exe kezelő futás közben képzett kulcsai: a futtató állapotai és az ablakcímek."""
    keys = {key for _patterns, key in literal(EXE / "runner.py", "_STAGES")}
    return keys | {"title.launch", "title.install", "title.manage"} | DESKTOP_KEYS["sloth-exe"]


DESKTOP_KEYS = desktop_keys()

# eszköz -> (csomag, további forrásfájlok, adatokból képzett kulcsok)
TOOLS = {
    "sloth-welcome": (WELCOME, [], welcome_keys),
    "sloth-installer": (INSTALLER, [INSTALL_HELPER], installer_keys),
    "sloth-exe": (EXE, [], exe_keys),
}


def used_keys(pkg, extra_files, extra_keys):
    keys = extra_keys()
    for f in list(pkg.glob("*.py")) + list((pkg / "qml").glob("*.qml")) + extra_files:
        text = f.read_text(encoding="utf-8")
        for m in KEY_PATTERN.finditer(text):
            keys.add(m.group(1) or m.group(2))
        for m in CONDITIONAL_PATTERN.finditer(text):
            keys |= set(re.findall(r'"([a-z_]+\.[a-z_.]+)"', m.group(1)))
    return keys


def _script(ch):
    name = unicodedata.name(ch, "")
    return next((s for s in ("LATIN", "CYRILLIC", "GREEK") if name.startswith(s)), None)


def mixed_words(text):
    """Szavak, amelyekben latin, cirill és görög betű keveredik."""
    return [w for w in re.findall(r"\w+", text) if len({_script(c) for c in w} - {None}) > 1]


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text))


def check(tool, pkg, extra_files, extra_keys):
    langs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((pkg / "translations").glob("*.json"))}
    source = langs[SOURCE]
    used = used_keys(pkg, extra_files, extra_keys)
    errors = 0
    print(f"== {tool} ({len(langs)} nyelv)")

    missing = sorted(used - source.keys())
    if missing:
        errors += 1
        print(f"HIBA: a kódban használt, de a {SOURCE}.json-ból hiányzó kulcsok:", *missing, sep="\n  ")
    unused = sorted(k for k in source.keys() - used if not k.startswith("_"))
    if unused:
        print(f"Figyelem: a {SOURCE}.json-ban van, de a kód nem használja:", *unused, sep="\n  ")

    for code, data in langs.items():
        if code == SOURCE:
            continue
        lacking = sorted(k for k in source if k not in data)
        extra = sorted(k for k in data if k not in source)
        wrong = sorted(k for k in data if k in source and placeholders(data[k]) != placeholders(source[k]))
        mixed = sorted(f"{k}: {', '.join(mixed_words(v))}" for k, v in data.items()
                       if not k.startswith("_") and mixed_words(v))
        hidden = sorted(k for k, v in data.items() if INVISIBLE.search(v))
        if hidden:
            errors += 1
            print(f"HIBA: {code}: láthatatlan karakter:", *hidden, sep="\n  ")
        if mixed:
            errors += 1
            print(f"HIBA: {code}: vegyes írásrendszerű szavak:", *mixed, sep="\n  ")
        if lacking:
            print(f"{code}: {len(lacking)} hiányzó fordítás (ezeknél angol/magyar szöveg látszik):", *lacking, sep="\n  ")
        if extra:
            errors += 1
            print(f"HIBA: {code}: ismeretlen kulcsok:", *extra, sep="\n  ")
        if wrong:
            errors += 1
            print(f"HIBA: {code}: eltérő {{helyőrzők}}:", *wrong, sep="\n  ")
    return errors


def main():
    errors = sum(check(tool, *args) for tool, args in TOOLS.items())
    # a .desktop fájlok a fordításokból készülnek; ha egy fordítás változott, újra kell írni őket
    if subprocess.run([sys.executable, str(REPO / "tools/gen_desktop_entries.py"), "--check"]).returncode:
        errors += 1
    print("Rendben." if not errors else f"{errors} hiba.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
