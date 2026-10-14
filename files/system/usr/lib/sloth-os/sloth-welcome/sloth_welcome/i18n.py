"""Fordítások: nyelvenként egy JSON a translations/ mappában.

A kulcsok pontokkal tagolt nevek ("welcome.title"); a szövegekben {név} alakú
helyőrzők lehetnek. Ha egy nyelvből hiányzik egy kulcs, az angol, végül a magyar
szöveg látszik. Új nyelv: a hu.json másolata új néven (pl. fr.json), a
"_language" mezőben a nyelv saját nevével ("Français").
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("sloth-welcome.i18n")

DIR = Path(__file__).resolve().parent / "translations"
SOURCE = "hu"     # a projekt nyelve: ebben teljes minden szöveg
FALLBACK = "en"   # ha egy nyelvből hiányzik valami

_cache = {}
_current = {}
_code = SOURCE


def _load(code):
    if code not in _cache:
        try:
            _cache[code] = json.loads((DIR / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("%s: %s", code, e)
            _cache[code] = {}
    return _cache[code]


def available():
    """[{"code": "hu", "name": "Magyar"}, …] a nyelv saját nevével, ábécérendben."""
    out = [{"code": p.stem, "name": _load(p.stem).get("_language", p.stem)} for p in DIR.glob("*.json")]
    return sorted(out, key=lambda x: x["name"].lower())


def system_language():
    """A rendszer nyelve (a telepítőben választott), ha van rá fordításunk; különben angol."""
    codes = {l["code"] for l in available()}
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for part in os.environ.get(var, "").split(":"):
            code = part.split(".")[0].split("_")[0].lower()
            if code in codes:
                return code
    return FALLBACK if FALLBACK in codes else SOURCE


def set_language(code):
    global _current, _code
    merged = {}
    for c in (SOURCE, FALLBACK, code):
        merged.update(_load(c))
    _current, _code = merged, code


def language():
    return _code


def strings():
    return dict(_current)


def tr(key, **args):
    text = _current.get(key, key)
    return text.format(**args) if args else text


set_language(system_language())
