#!/usr/bin/env python3
"""Collects Sloth Center's translatable texts (developer tool, not in the image).

In Sloth Center the English sentence itself is the key (sloth_center/i18n.py). This script collects the texts of
the tr("…"), N_("…") (Python) and L.t("…"), L.tf("…") (QML) calls, plus the start menu texts
(tools/gen_desktop_entries.py), and prints what a language's file lacks:
  python tools/extract_center_strings.py [language]   (default: hu)
  python tools/extract_center_strings.py --all        (every language; exits with 1 if anything is missing)
  python tools/extract_center_strings.py --list       (all texts as a JSON list)
"""
import ast
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "files/system/usr/lib/sloth-os/sloth-center/sloth_center"
QML_CALL = re.compile(r'\bL\.tf?\(\s*"((?:[^"\\]|\\.)*)"')


def desktop_strings():
    """Sloth Center's texts in the start menu entries (read from the generator's source, without importing it)."""
    src = (Path(__file__).resolve().parent / "gen_desktop_entries.py").read_text(encoding="utf-8")
    return [json.loads(m) for m in re.findall(r'\("sloth-center", ("(?:[^"\\]|\\.)*")\)', src)]


def strings():
    found = []
    for f in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("tr", "N_") \
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.append(node.args[0].value)
    for f in sorted((PKG / "qml").glob("*.qml")):
        found += [json.loads(f'"{m}"') for m in QML_CALL.findall(f.read_text(encoding="utf-8"))]
    return list(dict.fromkeys(found + desktop_strings()))


def report(all_strings, code):
    path = PKG / "translations" / f"{code}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    missing = [s for s in all_strings if s not in data]
    extra = [k for k in data if not k.startswith("_") and k not in all_strings]
    print(f"{len(all_strings)} texts, {code}: {len(missing)} missing, {len(extra)} unknown")
    for s in missing:
        print("  missing:", s)
    for s in extra:
        print("  unknown:", s)
    return 1 if missing or extra else 0


def main():
    all_strings = strings()
    if "--list" in sys.argv:
        print(json.dumps(all_strings, ensure_ascii=False, indent=1))
        return 0
    if "--all" in sys.argv:
        codes = sorted(p.stem for p in (PKG / "translations").glob("*.json") if p.stem != "en")
        return 1 if sum(report(all_strings, c) for c in codes) else 0
    code = next((a for a in sys.argv[1:] if not a.startswith("-")), "hu")
    return report(all_strings, code)


if __name__ == "__main__":
    sys.exit(main())
