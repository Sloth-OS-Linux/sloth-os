#!/usr/bin/env python3
"""Checks the translations of Sloth OS's own tools (Welcome, installer, .exe handler) (developer tool, not in the image).

It checks that:
  - every key used in the code and the catalog is in the English (source) file,
  - what the other languages lack (English is shown for those),
  - there are no unknown keys, and the {placeholders} match the English ones,
  - no word mixes Latin, Cyrillic or Greek letters (a typo, e.g. "Meglено"),
  - there are no invisible characters (soft hyphen, zero-width space).

Sloth Center (where the English sentence is the key) is checked by tools/extract_center_strings.py.

Usage: python tools/check_translations.py   (exits with 1 on errors)
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
APPEARANCE = REPO / "files/system/usr/lib/sloth-os/common/sloth_common/appearance.py"
INSTALLER = REPO / "iso/files/usr/lib/sloth-os/sloth-installer/sloth_installer"
INSTALL_HELPER = REPO / "iso/files/usr/libexec/sloth-os/sloth-install-helper"
EXE = REPO / "files/system/usr/lib/sloth-os/sloth-exe/sloth_exe"
SOURCE = "en"

# tr("…") in Python, t("…") in QML, and texts stored as keys ("error.…", "done.…", "account.error.…")
KEY_PATTERN = re.compile(r'\b(?:tr|t)\(\s*"([a-z_]+\.[\w.]*\w)"|"((?:error|done|account\.error)\.[a-z_]+)"')
# Conditional keys in QML: root.t(x ? "a.b" : "c.d")
CONDITIONAL_PATTERN = re.compile(r'root\.t\(([^()]*\?[^()]*)')
INVISIBLE = re.compile(r"[­​﻿]")  # soft hyphen, zero-width space, BOM


def desktop_keys():
    """The start menu entries' keys per tool (tools/gen_desktop_entries.py writes the .desktop files from them)."""
    keys = {}
    for fields in literal(REPO / "tools/gen_desktop_entries.py", "ENTRIES").values():
        for _name, value in fields:
            if isinstance(value, tuple):
                keys.setdefault(value[0], set()).add(value[1])
    return keys


def literal(path, name):
    """The value of a module-level list, read from the source (without importing, since gi is not available here)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def welcome_keys():
    """Sloth Welcome's keys built from data (catalog, color schemes, layouts)."""
    keys = set()
    for cat in literal(WELCOME / "catalog.py", "CATEGORIES"):
        keys |= {f"category.{cat['id']}.name", f"category.{cat['id']}.hint"}
        keys |= {f"app.{a['id']}" for a in cat["apps"]}
    # the color schemes and layouts are shared with Sloth Center (sloth_common.appearance)
    keys |= {f"scheme.{s['id']}" for s in literal(APPEARANCE, "COLOR_SCHEMES")}
    for kind in literal(APPEARANCE, "LAYOUTS"):
        keys |= {f"layout.{kind}.name", f"layout.{kind}.description"}
    return keys | DESKTOP_KEYS["sloth-welcome"]


def installer_keys():
    """The installer's keys built at run time: stages (sent by the helper) and the disk contents."""
    stages = {stage for _keys, stage, _pct in literal(INSTALL_HELPER, "STAGES")}
    keys = {f"stage.{s}" for s in stages | {"start", "verify", "partition", "shrink", "encrypt", "configure"}}
    # Disk encryption: password problems (returned by the controller as keys)
    keys |= {f"disk.encrypt.{p}" for p in ("mismatch", "short", "short_same")}
    # Installing next to Windows: explanations of the obstacles (sent by the helper, combined by the UI)
    keys |= {f"disk.beside.{p}" for p in literal(INSTALL_HELPER, "BESIDE_PROBLEMS")}
    return keys | {f"disk.contents.{c}" for c in ("empty", "windows", "linux", "other")} | DESKTOP_KEYS["sloth-installer"]


def exe_keys():
    """The .exe handler's keys built at run time: the runner's stages and the window titles."""
    keys = {key for _patterns, key in literal(EXE / "runner.py", "_STAGES")}
    return keys | {"title.launch", "title.install", "title.manage"} | DESKTOP_KEYS["sloth-exe"]


DESKTOP_KEYS = desktop_keys()

# tool -> (package, extra source files, keys built from data)
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
    """Words that mix Latin, Cyrillic and Greek letters."""
    return [w for w in re.findall(r"\w+", text) if len({_script(c) for c in w} - {None}) > 1]


def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", text))


def check(tool, pkg, extra_files, extra_keys):
    langs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((pkg / "translations").glob("*.json"))}
    source = langs[SOURCE]
    used = used_keys(pkg, extra_files, extra_keys)
    errors = 0
    print(f"== {tool} ({len(langs)} languages)")

    missing = sorted(used - source.keys())
    if missing:
        errors += 1
        print(f"ERROR: keys used in the code but missing from {SOURCE}.json:", *missing, sep="\n  ")
    unused = sorted(k for k in source.keys() - used if not k.startswith("_"))
    if unused:
        print(f"Warning: in {SOURCE}.json but not used by the code:", *unused, sep="\n  ")

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
            print(f"ERROR: {code}: invisible characters:", *hidden, sep="\n  ")
        if mixed:
            errors += 1
            print(f"ERROR: {code}: words with mixed scripts:", *mixed, sep="\n  ")
        if lacking:
            print(f"{code}: {len(lacking)} missing translations (English is shown for these):", *lacking, sep="\n  ")
        if extra:
            errors += 1
            print(f"ERROR: {code}: unknown keys:", *extra, sep="\n  ")
        if wrong:
            errors += 1
            print(f"ERROR: {code}: different {{placeholders}}:", *wrong, sep="\n  ")
    return errors


def main():
    errors = sum(check(tool, *args) for tool, args in TOOLS.items())
    # the .desktop files are generated from the translations; if one changed, they must be rewritten
    if subprocess.run([sys.executable, str(REPO / "tools/gen_desktop_entries.py"), "--check"]).returncode:
        errors += 1
    print("OK." if not errors else f"{errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
