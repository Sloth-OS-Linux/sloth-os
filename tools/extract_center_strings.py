#!/usr/bin/env python3
"""A Sloth Központ fordítandó szövegeinek kigyűjtése (fejlesztői segéd, nem kerül az image-be).

A Sloth Központban a magyar mondat maga a kulcs (sloth_center/i18n.py). Ez a script kigyűjti
a tr("…"), N_("…") (Python) és L.t("…"), L.tf("…") (QML) hívások szövegeit, és kiírja, mi
hiányzik egy nyelv fájljából:
  python tools/extract_center_strings.py [nyelv]      (alapból: en)
  python tools/extract_center_strings.py --list        (az összes szöveg JSON-listaként)
"""
import ast
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "files/system/usr/lib/sloth-os/sloth-center/sloth_center"
QML_CALL = re.compile(r'\bL\.tf?\(\s*"((?:[^"\\]|\\.)*)"')


def strings():
    found = []
    for f in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("tr", "N_") \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.append(node.args[0].value)
    for f in sorted((PKG / "qml").glob("*.qml")):
        found += [json.loads(f'"{m}"') for m in QML_CALL.findall(f.read_text(encoding="utf-8"))]
    return list(dict.fromkeys(found))


def main():
    all_strings = strings()
    if "--list" in sys.argv:
        print(json.dumps(all_strings, ensure_ascii=False, indent=1))
        return 0
    code = next((a for a in sys.argv[1:] if not a.startswith("-")), "en")
    path = PKG / "translations" / f"{code}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missing = [s for s in all_strings if s not in data]
    extra = [k for k in data if not k.startswith("_") and k not in all_strings]
    print(f"{len(all_strings)} szöveg, {code}: {len(missing)} hiányzik, {len(extra)} felesleges")
    for s in missing:
        print("  hiányzik:", s)
    for s in extra:
        print("  felesleges:", s)
    return 1 if missing or extra else 0


if __name__ == "__main__":
    sys.exit(main())
