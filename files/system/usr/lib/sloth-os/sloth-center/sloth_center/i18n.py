"""A Sloth Központ fordításai.

Itt a magyar szöveg maga a kulcs (mint a gettextnél): a kódban tr("Frissítés keresése…") áll,
a translations/<nyelv>.json a magyar mondathoz rendeli a fordítást. Ami egy nyelvből
hiányzik, angolul, végül magyarul jelenik meg. Változók: tr("{n} szolgáltatás", n=3).
A QML a "L" objektumon keresztül fordít: L.t("…"), L.tf("… {n} …", {n: 3}).
Táblázatokban a szöveg N_("…") jelölést kap, és felhasználáskor fordul le.
"""
from pathlib import Path

from PySide6.QtCore import QObject, Slot

from sloth_common.i18n import Catalog

catalog = Catalog(Path(__file__).resolve().parent / "translations")


def tr(text, **args):
    return catalog.tr(text, **args)


def N_(text):
    """Csak megjelöli a szöveget fordításra (táblázatokban); a fordítás felhasználáskor, tr()-rel történik."""
    return text


class Translator(QObject):
    """A QML oldali fordító (context property: "L")."""

    @Slot(str, result=str)
    def t(self, text):
        return catalog.tr(text)

    @Slot(str, "QVariantMap", result=str)
    def tf(self, text, args):
        return catalog.tr(text, **{k: v for k, v in args.items()})
