"""Translations for Sloth OS's own tools: one translations/ folder per tool, one JSON file per language.

Keys are dotted names ("welcome.title"), except in Sloth Center, where the English sentence itself is the key.
Texts may contain {name} placeholders. If a language lacks a key, the English text is shown (in Sloth Center: the
key itself). New language: a copy of en.json under a new name (e.g. fr.json), with the language's own name in the
"_language" field ("Français").

Language codes follow the glibc locale names (hu, pt_BR, zh_TW).
"""
import json
import logging
import os
import unicodedata
from pathlib import Path

log = logging.getLogger("sloth-os.i18n")

SOURCE = "en"     # the project language: every text is complete in it, and it is the fallback

# Right-to-left languages: the interface is mirrored
RTL = {"ar", "he", "fa", "ur"}
# Used when there is no translation for the exact variant (e.g. Hong Kong Chinese -> Traditional)
ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN", "no": "nb", "pt_PT": "pt",
           "bn": "bn_IN"}


def sort_key(name):
    """Sorting without accents ("Čeština" under C, not after the Latin names)."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return plain.casefold()


def match(locale_name, codes):
    """"pt_BR.UTF-8" -> "pt_BR", "de_AT.UTF-8" -> "de", "sr_RS@latin" -> "sr"; None if there is no match."""
    name = locale_name.split(".")[0].split("@")[0]
    lang = name.split("_")[0].lower()
    for cand in (name, ALIASES.get(name), lang, ALIASES.get(lang)):
        if cand and cand in codes:
            return cand
    return None


def is_rtl(code):
    return code.split("_")[0] in RTL


class Catalog:
    """The translations of one tool (e.g. Sloth Welcome), starting in the system language."""

    def __init__(self, directory):
        self.dir = Path(directory)
        self._cache = {}
        self._current = {}
        self._code = SOURCE
        self.set_language(self.system_language())

    def _load(self, code):
        if code not in self._cache:
            try:
                self._cache[code] = json.loads((self.dir / f"{code}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                log.warning("%s: %s", code, e)
                self._cache[code] = {}
        return self._cache[code]

    def available(self):
        """[{"code": "hu", "name": "Magyar"}, …] with each language's own name, sorted alphabetically."""
        out = [{"code": p.stem, "name": self._load(p.stem).get("_language", p.stem)}
               for p in self.dir.glob("*.json")]
        return sorted(out, key=lambda x: sort_key(x["name"]))

    def system_language(self):
        """The system language (chosen in the installer) if we have a translation for it; otherwise English."""
        codes = {l["code"] for l in self.available()}
        for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            for part in os.environ.get(var, "").split(":"):
                code = match(part, codes) if part and part not in ("C", "POSIX") else None
                if code:
                    return code
        return SOURCE

    def set_language(self, code):
        merged = {}
        for c in (SOURCE,) if code == SOURCE else (SOURCE, code):
            merged.update(self._load(c))
        self._current, self._code = merged, code

    def language(self):
        return self._code

    def is_rtl(self):
        return is_rtl(self._code)

    def strings(self):
        return dict(self._current)

    def tr(self, key, **args):
        text = self._current.get(key, key)
        return text.format(**args) if args else text
