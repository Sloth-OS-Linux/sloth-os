#!/usr/bin/env python3
"""A Sloth Üdvözlő fordításainak ellenőrzése (fejlesztői segéd, nem kerül az image-be).

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
import sys
import unicodedata
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "files/system/usr/lib/sloth-os/sloth-welcome/sloth_welcome"
TRANSLATIONS = PKG / "translations"
SOURCE = "hu"


def literal(path, name):
    """Egy modulszintű lista értéke a forrásból (importálás nélkül, mert a gi itt nincs meg)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def used_keys():
    keys = set()
    for cat in literal(PKG / "catalog.py", "CATEGORIES"):
        keys |= {f"category.{cat['id']}.name", f"category.{cat['id']}.hint"}
        keys |= {f"app.{a['id']}" for a in cat["apps"]}
    keys |= {f"scheme.{s['id']}" for s in literal(PKG / "desktop.py", "COLOR_SCHEMES")}
    for l in literal(PKG / "desktop.py", "LAYOUTS"):
        keys |= {f"layout.{l['id']}.name", f"layout.{l['id']}.description"}
    # tr("…") a Pythonban, t("…") a QML-ben, valamint a kulcsként tárolt szövegek ("error.…", "done.…")
    pattern = re.compile(r'''\b(?:tr|t)\(\s*"([a-z_]+\.[\w.]+)"|"((?:error|done)\.[a-z_]+)"''')
    for f in list(PKG.glob("*.py")) + list((PKG / "qml").glob("*.qml")):
        for m in pattern.finditer(f.read_text(encoding="utf-8")):
            keys.add(m.group(1) or m.group(2))
    # QML-ben feltételes kulcsok: root.t(x ? "a.b" : "c.d")
    for f in (PKG / "qml").glob("*.qml"):
        for m in re.finditer(r'root\.t\(([^()]*\?[^()]*)', f.read_text(encoding="utf-8")):
            keys |= set(re.findall(r'"([a-z_]+\.[a-z_.]+)"', m.group(1)))
    return keys


def _script(ch):
    name = unicodedata.name(ch, "")
    return next((s for s in ("LATIN", "CYRILLIC", "GREEK") if name.startswith(s)), None)


def mixed_words(text):
    """Szavak, amelyekben latin, cirill és görög betű keveredik."""
    return [w for w in re.findall(r"\w+", text) if len({_script(c) for c in w} - {None}) > 1]


INVISIBLE = re.compile(r"[\u00ad\u200b\ufeff]")  # feltételes elválasztó, nulla szélességű szóköz, BOM


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text))


def main():
    langs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TRANSLATIONS.glob("*.json"))}
    source = langs[SOURCE]
    used = used_keys()
    errors = 0

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

    print("Rendben." if not errors else f"{errors} hiba.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
