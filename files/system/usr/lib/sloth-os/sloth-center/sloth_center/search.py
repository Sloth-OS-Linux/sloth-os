"""The search at the top of Sloth Center's sidebar (Main.qml): what it looks through.

A Sloth Center page is found by its name and by the short texts on it (its titles, labels and buttons: the L.t()
texts of its QML file of at most SHORT words; the long explanations mention too much), in English and in the user's
language. So "password" finds Account and security, "jelszó" too in Hungarian, with no keyword lists to keep up in
50 languages. KDE's pages bring their own names, descriptions
and keywords (KcmCatalog, already translated by KDE).

Texts are compared without case, spaces and punctuation: "wifi" finds "Wi-Fi", "nightlight" finds "Night Light".

QML: searchIndex.normalize(text), searchIndex.pageText(qmlFile) (normalized, the page's texts one per line).
"""
import re
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from .i18n import catalog

QML = Path(__file__).resolve().parent / "qml"
# the texts a QML file shows: L.t("…") and L.tf("…", {…}) (a placeholder like {n} is left out of the search)
LITERAL = re.compile(r'\bL\.tf?\(\s*"((?:[^"\\]|\\.)*)"')
PLACEHOLDER = re.compile(r"\{\w+\}")
SHORT = 6  # words: a title, a label, a button (tried in the VM: with the explanations "wifi" found eight pages)


def normalize(text):
    """Lower case, no spaces or punctuation (letters of every script and digits stay)."""
    return re.sub(r"[\W_]+", "", (text or "").casefold())


@lru_cache(maxsize=None)
def page_text(qml_file, qml_dir=QML):
    """The normalized texts of one page (English and translated), one per line; "" if the file is not there."""
    try:
        source = (Path(qml_dir) / Path(qml_file).name).read_text(encoding="utf-8")
    except OSError:
        return ""
    seen = []
    for raw in LITERAL.findall(source):
        english = raw.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        if len(PLACEHOLDER.sub(" ", english).split()) > SHORT:
            continue
        for text in (english, catalog.tr(english) if "{" not in english else catalog.tr(english, **_blank(english))):
            t = normalize(PLACEHOLDER.sub(" ", text))
            if t and t not in seen:
                seen.append(t)
    return "\n".join(seen)


def _blank(text):
    """Placeholders filled with nothing, so a text with {n} can still be translated for the search."""
    return {name: "" for name in re.findall(r"\{(\w+)\}", text)}


class SearchIndex(QObject):
    @Slot(str, result=str)
    def normalize(self, text):
        return normalize(text)

    @Slot(str, result=str)
    def pageText(self, qml_file):
        return page_text(qml_file)
