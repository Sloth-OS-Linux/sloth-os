"""Sloth Center's translations.

Here the English text itself is the key (as with gettext): the code says tr("Looking for updates…"), and
translations/<language>.json maps that sentence to its translation. Whatever a language lacks is shown in
English. Placeholders: tr("{n} services", n=3).
QML translates through the "L" object: L.t("…"), L.tf("… {n} …", {n: 3}).
In tables a text is marked with N_("…") and translated when it is used.
"""
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from sloth_common.i18n import Catalog

catalog = Catalog(Path(__file__).resolve().parent / "translations")


def tr(text, **args):
    return catalog.tr(text, **args)


def N_(text):
    """Only marks a text for translation (in tables); it is translated with tr() when used."""
    return text


class Translator(QObject):
    """The translator on the QML side (context property: "L")."""

    @Slot(str, result=str)
    def t(self, text):
        return catalog.tr(text)

    @Slot(str, "QVariantMap", result=str)
    def tf(self, text, args):
        return catalog.tr(text, **{k: v for k, v in args.items()})
