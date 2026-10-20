"""Fordítások a Sloth OS saját eszközeihez: eszközönként egy translations/ mappa, nyelvenként egy JSON.

A kulcsok pontokkal tagolt nevek ("welcome.title"); a szövegekben {név} alakú
helyőrzők lehetnek. Ha egy nyelvből hiányzik egy kulcs, az angol, végül a magyar
szöveg látszik. Új nyelv: a hu.json másolata új néven (pl. fr.json), a
"_language" mezőben a nyelv saját nevével ("Français").

A nyelvkódok a glibc locale-nevekhez igazodnak (hu, pt_BR, zh_TW).
"""
import json
import logging
import os
import unicodedata
from pathlib import Path

log = logging.getLogger("sloth-os.i18n")

SOURCE = "hu"     # a projekt nyelve: ebben teljes minden szöveg
FALLBACK = "en"   # ha egy nyelvből hiányzik valami

# Jobbról balra írt nyelvek: a felület tükrözve jelenik meg
RTL = {"ar", "he", "fa", "ur"}
# Ha a pontos változatra nincs fordítás, ezt használjuk (pl. hongkongi kínai -> hagyományos)
ALIASES = {"zh_HK": "zh_TW", "zh_MO": "zh_TW", "zh_SG": "zh_CN", "zh": "zh_CN", "no": "nb", "pt_PT": "pt",
           "bn": "bn_IN"}


def sort_key(name):
    """Ékezet nélküli rendezés ("Čeština" a C-nél, ne a latin betűs nevek után)."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return plain.casefold()


def match(locale_name, codes):
    """"pt_BR.UTF-8" -> "pt_BR", "de_AT.UTF-8" -> "de", "sr_RS@latin" -> "sr"; None, ha nincs ilyen."""
    name = locale_name.split(".")[0].split("@")[0]
    lang = name.split("_")[0].lower()
    for cand in (name, ALIASES.get(name), lang, ALIASES.get(lang)):
        if cand and cand in codes:
            return cand
    return None


def is_rtl(code):
    return code.split("_")[0] in RTL


class Catalog:
    """Egy eszköz fordításai (pl. a Sloth Üdvözlőé), a rendszer nyelvén indulva."""

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
        """[{"code": "hu", "name": "Magyar"}, …] a nyelv saját nevével, ábécérendben."""
        out = [{"code": p.stem, "name": self._load(p.stem).get("_language", p.stem)}
               for p in self.dir.glob("*.json")]
        return sorted(out, key=lambda x: sort_key(x["name"]))

    def system_language(self):
        """A rendszer nyelve (a telepítőben választott), ha van rá fordításunk; különben angol."""
        codes = {l["code"] for l in self.available()}
        for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            for part in os.environ.get(var, "").split(":"):
                code = match(part, codes) if part and part not in ("C", "POSIX") else None
                if code:
                    return code
        return FALLBACK if FALLBACK in codes else SOURCE

    def set_language(self, code):
        merged = {}
        # Magyarul nem kell az angol tartalék: ahol a magyar szöveg maga a kulcs (Sloth Központ), és a hu.json-ban
        # nincs meg, ott különben az angol látszana
        for c in (SOURCE,) if code == SOURCE else (SOURCE, FALLBACK, code):
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
